"""
Vectorless Structured RAG (Text-to-SQL + Grounded Response Generation).
Supports Gemini, OpenAI, and an offline rule-based heuristic fallback.
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
        self.provider = settings.LLM_PROVIDER
        self.gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.model = settings.LLM_MODEL

    async def generate_sql(self, user_query: str) -> str:
        """Call 1: Natural Language -> Safe SQL Query."""
        # Try configured LLM provider if key available
        if self.gemini_key and self.provider == "gemini":
            try:
                return await self._call_gemini_sql(user_query)
            except Exception as e:
                print(f"[LLM WARNING] Gemini SQL call failed ({e}). Falling back to offline heuristic.")

        if self.openai_key and self.provider == "openai":
            try:
                return await self._call_openai_sql(user_query)
            except Exception as e:
                print(f"[LLM WARNING] OpenAI SQL call failed ({e}). Falling back to offline heuristic.")

        # Offline heuristic fallback
        return self._heuristic_sql_generator(user_query)

    async def synthesize_response(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        """Call 2: Retrieved SQL Rows + User Query -> Natural Language Answer."""
        if not records:
            return "No matching student records found for your query."

        if self.gemini_key and self.provider == "gemini":
            try:
                return await self._call_gemini_synthesis(user_query, records)
            except Exception as e:
                print(f"[LLM WARNING] Gemini synthesis failed ({e}). Falling back to grounded template.")

        if self.openai_key and self.provider == "openai":
            try:
                return await self._call_openai_synthesis(user_query, records)
            except Exception as e:
                print(f"[LLM WARNING] OpenAI synthesis failed ({e}). Falling back to grounded template.")

        # Grounded template synthesizer
        return self._template_synthesis(user_query, records)

    async def _call_gemini_sql(self, user_query: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SCHEMA_SYSTEM_PROMPT}\n\nUser Question: {user_query}"}]
                }
            ],
            "generationConfig": {"temperature": 0.0}
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return raw_text.strip()

    async def _call_gemini_synthesis(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_key}"
        prompt = (
            f"{SYNTHESIZER_SYSTEM_PROMPT}\n\n"
            f"User Question: \"{user_query}\"\n\n"
            f"Retrieved Records: {records}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    async def _call_openai_sql(self, user_query: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SCHEMA_SYSTEM_PROMPT},
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.0
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_openai_synthesis(self, user_query: str, records: List[Dict[str, Any]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        prompt = f"User Question: \"{user_query}\"\n\nRetrieved Records: {records}"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

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
