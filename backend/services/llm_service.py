"""
Vectorless Structured RAG (Text-to-SQL + Grounded Response Generation).
Supports:
1. Primary Provider: Groq (ultra-fast inference) — keys #1 -> #2 -> #3
2. Alternate Fallback Provider: NVIDIA NIM (high quality model fallback) — keys #1 -> #2 -> #3
3. Safety Net Fallback: Offline deterministic heuristic + template synthesizer
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx
from backend.app.config import settings

SCHEMA_SYSTEM_PROMPT = """You are an expert PostgreSQL database engineer for a university student system.
Your sole job is to translate the user's natural language question into a single, valid, safe PostgreSQL SELECT query.

Database Schema:
Table: students
Columns:
  - student_id: VARCHAR(20) (Primary Key, e.g., 'STU001')
  - name: VARCHAR(100) (Student full name)
  - department: VARCHAR(50) (e.g., 'Computer Science', 'Information Technology', 'Artificial Intelligence & Data Science', 'Electronics & Communication', 'Mechanical Engineering', 'Civil Engineering')
  - year: INTEGER (Current academic year: 1, 2, 3, 4)
  - cgpa: REAL (Cumulative GPA, range 0.00 to 10.00)
  - email: VARCHAR(120) (Student email address)
  - skills: TEXT (Comma-separated skills, e.g., 'Python, PyTorch, AI, Docker')
  - placement_status: VARCHAR(20) ('Placed', 'Eligible', 'Not Eligible')

Rules:
1. Generate ONLY standard PostgreSQL read-only SELECT statements.
2. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or GRANT statements.
3. For text searches in skills or departments, use case-insensitive matching: LIKE or ILIKE (e.g., `skills LIKE '%ai%'` or `skills LIKE '%AI%'`).
4. Output ONLY the raw SQL query with no markdown backticks, no commentary, and no explanation.
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are a helpful student academic advisor assistant.
Answer the user's question accurately using ONLY the provided database query results.
Do not invent or assume information not present in the records.

The full result set is shown to the user as a table directly below your answer, so:
- Reply in 1-3 short sentences of plain natural language.
- Do NOT list every record, and do NOT use bullet points, numbered lists, headings or tables.
- State how many records matched (use the count given), then one or two useful highlights,
  e.g. the highest CGPA, the most common department, or how many are placed.
- For a single number (a count or an average), simply state it.
- You may bold one or two key names or numbers with **double asterisks**.
"""

class LLMService:
    def __init__(self):
        # Groq (Primary) — keys #1 -> #2 -> #3
        self.groq_keys = [
            settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", ""),
            settings.GROQ_API_KEY_2,
            settings.GROQ_API_KEY_3,
        ]
        self.groq_model = settings.GROQ_MODEL
        self.groq_base_url = settings.GROQ_BASE_URL.rstrip("/")

        # NVIDIA NIM (Alternate Fallback) — keys #1 -> #2 -> #3
        self.nvidia_keys = [
            settings.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", ""),
            settings.NVIDIA_API_KEY_2,
            settings.NVIDIA_API_KEY_3,
        ]
        self.nvidia_model = settings.NVIDIA_MODEL
        self.nvidia_base_url = settings.NVIDIA_BASE_URL.rstrip("/")

        # Strategy
        self.primary_provider = settings.PRIMARY_LLM_PROVIDER
        self.fallback_provider = settings.FALLBACK_LLM_PROVIDER

    def _provider_chain(self) -> List[Tuple[str, str, str, str]]:
        """
        Failover order as (name, base_url, api_key, model):
        Groq #1 -> #2 -> #3 -> NVIDIA NIM #1 -> #2 -> #3. Unset keys are skipped.
        """
        chain = []
        if self.primary_provider == "groq":
            chain += [(f"Groq #{i}", self.groq_base_url, key, self.groq_model)
                      for i, key in enumerate(self.groq_keys, start=1)]
        chain += [(f"NVIDIA NIM #{i}", self.nvidia_base_url, key, self.nvidia_model)
                  for i, key in enumerate(self.nvidia_keys, start=1)]
        return [p for p in chain if p[2]]

    async def generate_sql(self, user_query: str) -> str:
        """
        Translates natural language to SQL with Groq -> NVIDIA key failover -> Heuristic redundancy.
        """
        for name, base_url, api_key, model in self._provider_chain():
            try:
                sql = await self._call_openai_compatible_sql(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    user_query=user_query,
                    provider_name=name
                )
                print(f"[LLM INFO] SQL generated successfully via {name} ({model})")
                return sql
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] {name} SQL call failed: {e}. Trying next provider...")

        # Final Safety Net: Offline heuristic generator
        print("[LLM INFO] Using offline heuristic SQL generator safety net.")
        return self._heuristic_sql_generator(user_query)

    async def synthesize_response(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        """
        Synthesizes grounded conversational response with Groq -> NVIDIA key failover -> Template redundancy.
        """
        if not records:
            return "No matching student records found for your query."

        for name, base_url, api_key, model in self._provider_chain():
            try:
                return await self._call_openai_compatible_synthesis(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    user_query=user_query,
                    records=records,
                    provider_name=name
                )
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] {name} synthesis failed: {e}. Trying next provider...")

        # Final Safety Net: Grounded template synthesis
        return self._template_synthesis(user_query, records)

    async def _call_openai_compatible_sql(
        self, base_url: str, api_key: str, model: str, user_query: str, provider_name: str
    ) -> str:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SCHEMA_SYSTEM_PROMPT},
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.0,
            "max_tokens": 250
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"{provider_name} returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content

    async def _call_openai_compatible_synthesis(
        self, base_url: str, api_key: str, model: str, user_query: str, records: List[Dict[str, Any]], provider_name: str
    ) -> str:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            f"User Question: \"{user_query}\"\n\n"
            f"Retrieved Records ({len(records)} found):\n{records[:10]}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 300
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"{provider_name} returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content

    def _heuristic_sql_generator(self, query: str) -> str:
        """Deterministic offline rule-based parser for common queries."""
        q = query.lower()
        where_clauses = []

        # CGPA threshold
        cgpa_match = re.search(r"(?:cgpa|cgps|gpa)\s*(?:greater than|>|above|>=)\s*([0-9.]+)", q)
        if cgpa_match:
            val = float(cgpa_match.group(1))
            where_clauses.append(f"cgpa > {val}")
        else:
            cgpa_less = re.search(r"(?:cgpa|cgps|gpa)\s*(?:less than|<|below|<=)\s*([0-9.]+)", q)
            if cgpa_less:
                val = float(cgpa_less.group(1))
                where_clauses.append(f"cgpa < {val}")

        # Skills
        for skill in ["ai", "machine learning", "python", "pytorch", "react", "docker", "aws", "kubernetes", "java", "c++", "rust", "go", "data science"]:
            if re.search(r"\b" + re.escape(skill) + r"\b", q):
                where_clauses.append(f"LOWER(skills) LIKE '%{skill}%'")

        # Placement status
        if "unplaced" in q or "not placed" in q or "not eligible" in q:
            where_clauses.append("placement_status != 'Placed'")
        elif "placed" in q:
            where_clauses.append("placement_status = 'Placed'")
        elif "eligible" in q:
            where_clauses.append("placement_status = 'Eligible'")

        # Department
        if "cse" in q or "computer science" in q:
            where_clauses.append("LOWER(department) LIKE '%computer science%'")
        elif "ai & ds" in q or "data science" in q and "department" in q:
            where_clauses.append("LOWER(department) LIKE '%artificial intelligence%'")
        elif "information technology" in q or "it dept" in q:
            where_clauses.append("LOWER(department) LIKE '%information technology%'")
        elif "ece" in q or "electronics" in q:
            where_clauses.append("LOWER(department) LIKE '%electronics%'")
        elif "mech" in q or "mechanical" in q:
            where_clauses.append("LOWER(department) LIKE '%mechanical%'")
        elif "civil" in q:
            where_clauses.append("LOWER(department) LIKE '%civil%'")

        # Build query
        base_query = "SELECT student_id, name, department, year, cgpa, email, skills, placement_status FROM students"
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        
        base_query += " ORDER BY cgpa DESC LIMIT 20;"
        return base_query

    def _template_synthesis(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        # Short summary only — the frontend renders the full records as a table below it.
        count = len(records)
        summary = f"Found **{count}** record{'s' if count != 1 else ''} matching your request."
        with_cgpa = [r for r in records if isinstance(r.get("cgpa"), (int, float)) and r.get("name")]
        if with_cgpa:
            top = max(with_cgpa, key=lambda r: r["cgpa"])
            summary += f" The highest CGPA among them is **{top['name']}** with {top['cgpa']}."
        return summary

llm_service = LLMService()
