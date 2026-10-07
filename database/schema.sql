-- ====================================================================
-- HackQubit 2.0 - Problem 18: Student Academic & Placement Database
-- Schema definition for 'students' table (PostgreSQL & SQLite compatible)
-- ====================================================================

CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    cgpa REAL NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    skills TEXT NOT NULL,
    placement_status VARCHAR(20) NOT NULL
);

-- Indexes for high-frequency search and filter queries
CREATE INDEX IF NOT EXISTS idx_students_cgpa ON students(cgpa);
CREATE INDEX IF NOT EXISTS idx_students_dept ON students(department);
CREATE INDEX IF NOT EXISTS idx_students_placement ON students(placement_status);
