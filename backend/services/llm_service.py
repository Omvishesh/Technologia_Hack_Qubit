"""
Vectorless Structured RAG (Text-to-SQL + Grounded Response Generation).
Supports:
1. Primary Provider: Groq (ultra-fast inference)
2. Alternate Fallback Provider: NVIDIA NIM (high quality model fallback)
3. Safety Net Fallback: Offline deterministic heuristic + template synthesizer
"""
import os
import re
from typing import Any, Dict, List, Optional
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
Answer the user's question accurately and concisely using ONLY the provided database query results.
Do not invent or assume information not present in the records.
If no records matched, inform the user clearly.
Highlight the students' names, CGPAs, departments, and matching skills.
"""

class LLMService:
    def __init__(self):
        # Groq (Primary)
        self.groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.groq_model = settings.GROQ_MODEL
        self.groq_base_url = settings.GROQ_BASE_URL.rstrip("/")

        # NVIDIA NIM (Alternate Fallback)
        self.nvidia_key = settings.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
        self.nvidia_model = settings.NVIDIA_MODEL
        self.nvidia_base_url = settings.NVIDIA_BASE_URL.rstrip("/")

        # Strategy
        self.primary_provider = settings.PRIMARY_LLM_PROVIDER
        self.fallback_provider = settings.FALLBACK_LLM_PROVIDER

    async def generate_sql(self, user_query: str) -> str:
        """
        Translates natural language to SQL with Primary -> Fallback -> Heuristic redundancy.
        """
        # 1. Attempt Primary Provider (Groq)
        if self.groq_key and self.primary_provider == "groq":
            try:
                sql = await self._call_openai_compatible_sql(
                    base_url=self.groq_base_url,
                    api_key=self.groq_key,
                    model=self.groq_model,
                    user_query=user_query,
                    provider_name="Groq"
                )
                print(f"[LLM INFO] SQL generated successfully via Primary (Groq / {self.groq_model})")
                return sql
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] Primary Groq call failed: {e}. Switching to alternate fallback (NVIDIA NIM)...")

        # 2. Attempt Alternate Fallback Provider (NVIDIA NIM)
        if self.nvidia_key:
            try:
                sql = await self._call_openai_compatible_sql(
                    base_url=self.nvidia_base_url,
                    api_key=self.nvidia_key,
                    model=self.nvidia_model,
                    user_query=user_query,
                    provider_name="NVIDIA NIM"
                )
                print(f"[LLM INFO] SQL generated successfully via Alternate Fallback (NVIDIA NIM / {self.nvidia_model})")
                return sql
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] Alternate NVIDIA call failed: {e}. Switching to offline heuristic...")

        # 3. Final Safety Net: Offline heuristic generator
        print("[LLM INFO] Using offline heuristic SQL generator safety net.")
        return self._heuristic_sql_generator(user_query)

    async def synthesize_response(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        """
        Synthesizes grounded conversational response with Primary -> Fallback -> Template redundancy.
        """
        if not records:
            return "No matching student records found for your query."

        # 1. Attempt Primary Provider (Groq)
        if self.groq_key and self.primary_provider == "groq":
            try:
                resp = await self._call_openai_compatible_synthesis(
                    base_url=self.groq_base_url,
                    api_key=self.groq_key,
                    model=self.groq_model,
                    user_query=user_query,
                    records=records,
                    provider_name="Groq"
                )
                return resp
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] Primary Groq synthesis failed: {e}. Switching to alternate fallback (NVIDIA NIM)...")

        # 2. Attempt Alternate Fallback Provider (NVIDIA NIM)
        if self.nvidia_key:
            try:
                resp = await self._call_openai_compatible_synthesis(
                    base_url=self.nvidia_base_url,
                    api_key=self.nvidia_key,
                    model=self.nvidia_model,
                    user_query=user_query,
                    records=records,
                    provider_name="NVIDIA NIM"
                )
                return resp
            except Exception as e:
                print(f"[LLM FALLBACK ALERT] Alternate NVIDIA synthesis failed: {e}. Switching to template synthesizer...")

        # 3. Final Safety Net: Grounded template synthesis
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
            "max_tokens": 600
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
        count = len(records)
        lines = [f"Found {count} student(s) matching your request:\n"]
        for idx, r in enumerate(records[:10], start=1):
            name = r.get("name", "N/A")
            dept = r.get("department", "N/A")
            year = r.get("year", "N/A")
            cgpa = r.get("cgpa", "N/A")
            skills = r.get("skills", "N/A")
            status = r.get("placement_status", "N/A")
            lines.append(f"{idx}. **{name}** ({dept}, Year {year}) — **CGPA: {cgpa}** | Skills: *{skills}* | Status: `{status}`")
        if count > 10:
            lines.append(f"\n*(Showing top 10 of {count} matching records)*")
        return "\n".join(lines)

llm_service = LLMService()
