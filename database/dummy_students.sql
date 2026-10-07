-- ====================================================================
-- HackQubit 2.0 - Problem 18: 50 fictional students for local PostgreSQL
-- Load:  psql -U postgres -h localhost -d hackqubit_students -f database/dummy_students.sql
-- Safe to re-run (CREATE ... IF NOT EXISTS, ON CONFLICT DO NOTHING).
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

CREATE INDEX IF NOT EXISTS idx_students_cgpa ON students(cgpa);
CREATE INDEX IF NOT EXISTS idx_students_dept ON students(department);
CREATE INDEX IF NOT EXISTS idx_students_placement ON students(placement_status);

INSERT INTO students (student_id, name, department, year, cgpa, email, skills, placement_status) VALUES
('STU101', 'Aditya Menon', 'Computer Science', 1, 6.98, 'aditya.menon@campus.edu', 'React, Go, Machine Learning, SQL', 'Not Eligible'),
('STU102', 'Riya Kapoor', 'Computer Science', 3, 7.98, 'riya.kapoor@campus.edu', 'AI, Go, AWS, React, Python', 'Eligible'),
('STU103', 'Vivek Narayan', 'Computer Science', 3, 9.20, 'vivek.narayan@campus.edu', 'Python, System Design, AWS, Docker, React', 'Eligible'),
('STU104', 'Sakshi Agarwal', 'Computer Science', 3, 9.00, 'sakshi.agarwal@campus.edu', 'Docker, Kubernetes, SQL, Java, AI', 'Eligible'),
('STU105', 'Harshit Bhardwaj', 'Computer Science', 1, 7.32, 'harshit.bhardwaj@campus.edu', 'System Design, Machine Learning, Go, Node.js', 'Not Eligible'),
('STU106', 'Ishaan Chatterjee', 'Computer Science', 1, 7.83, 'ishaan.chatterjee@campus.edu', 'Docker, AWS, Kubernetes, Java, System Design', 'Not Eligible'),
('STU107', 'Mehak Arora', 'Computer Science', 4, 6.39, 'mehak.arora@campus.edu', 'SQL, Go, AWS, Kubernetes, AI', 'Not Eligible'),
('STU108', 'Sahil Qureshi', 'Computer Science', 2, 7.43, 'sahil.qureshi@campus.edu', 'Go, AWS, SQL, System Design, Python', 'Not Eligible'),
('STU109', 'Nisha Ramesh', 'Computer Science', 3, 8.16, 'nisha.ramesh@campus.edu', 'Machine Learning, Go, Kubernetes, AWS', 'Eligible'),
('STU110', 'Kabir Malik', 'Computer Science', 1, 6.44, 'kabir.malik@campus.edu', 'Java, System Design, AWS, Machine Learning', 'Not Eligible'),
('STU111', 'Aishwarya Kulkarni', 'Computer Science', 4, 9.85, 'aishwarya.kulkarni@campus.edu', 'SQL, Kubernetes, System Design, Node.js, AI', 'Eligible'),
('STU112', 'Dhruv Khanna', 'Computer Science', 3, 7.41, 'dhruv.khanna@campus.edu', 'AI, Kubernetes, Machine Learning, React, Node.js', 'Eligible'),
('STU113', 'Lavanya Krishnan', 'Artificial Intelligence & Data Science', 4, 8.48, 'lavanya.krishnan@campus.edu', 'Pandas, Computer Vision, TensorFlow, AI, Deep Learning', 'Placed'),
('STU114', 'Parth Trivedi', 'Artificial Intelligence & Data Science', 3, 8.03, 'parth.trivedi@campus.edu', 'NLP, Pandas, Python, PyTorch, Deep Learning', 'Eligible'),
('STU115', 'Anjali Rawat', 'Artificial Intelligence & Data Science', 3, 8.35, 'anjali.rawat@campus.edu', 'Computer Vision, Deep Learning, NLP, LLMs, Python', 'Eligible'),
('STU116', 'Rohit Banerjee', 'Artificial Intelligence & Data Science', 3, 7.16, 'rohit.banerjee@campus.edu', 'TensorFlow, Machine Learning, AI, NLP, SQL', 'Eligible'),
('STU117', 'Sanya Bhatia', 'Artificial Intelligence & Data Science', 3, 8.02, 'sanya.bhatia@campus.edu', 'SQL, AI, LLMs, Machine Learning', 'Eligible'),
('STU118', 'Arnav Mukherjee', 'Artificial Intelligence & Data Science', 3, 8.00, 'arnav.mukherjee@campus.edu', 'LLMs, TensorFlow, Deep Learning, Python, Pandas', 'Eligible'),
('STU119', 'Diya Fernandes', 'Artificial Intelligence & Data Science', 4, 6.27, 'diya.fernandes@campus.edu', 'Deep Learning, Pandas, AI, Computer Vision, PyTorch', 'Not Eligible'),
('STU120', 'Yuvraj Chauhan', 'Artificial Intelligence & Data Science', 1, 7.13, 'yuvraj.chauhan@campus.edu', 'Machine Learning, NLP, Deep Learning, Pandas, SQL', 'Not Eligible'),
('STU121', 'Prachi Kulshreshtha', 'Artificial Intelligence & Data Science', 4, 7.13, 'prachi.kulshreshtha@campus.edu', 'Deep Learning, Pandas, AI, NLP, Python', 'Eligible'),
('STU122', 'Aman Siddiqui', 'Artificial Intelligence & Data Science', 4, 7.48, 'aman.siddiqui@campus.edu', 'Machine Learning, Python, TensorFlow, Pandas, NLP', 'Eligible'),
('STU123', 'Keerthi Subramanian', 'Information Technology', 4, 8.95, 'keerthi.subramanian@campus.edu', 'Linux, AWS, React, AI, Django', 'Placed'),
('STU124', 'Rudra Pratap', 'Information Technology', 4, 8.15, 'rudra.pratap@campus.edu', 'Cloud, Cybersecurity, Django, DevOps', 'Placed'),
('STU125', 'Ira Sengupta', 'Information Technology', 3, 8.14, 'ira.sengupta@campus.edu', 'JavaScript, Django, Angular, AI, AWS', 'Eligible'),
('STU126', 'Tejas Patil', 'Information Technology', 3, 9.33, 'tejas.patil@campus.edu', 'Linux, Django, AI, JavaScript', 'Eligible'),
('STU127', 'Shalini Murthy', 'Information Technology', 1, 6.54, 'shalini.murthy@campus.edu', 'Angular, AI, DevOps, SQL', 'Not Eligible'),
('STU128', 'Faizan Ahmed', 'Information Technology', 3, 7.72, 'faizan.ahmed@campus.edu', 'React, DevOps, SQL, Angular, Linux', 'Eligible'),
('STU129', 'Esha Thakur', 'Information Technology', 2, 6.00, 'esha.thakur@campus.edu', 'SQL, Linux, Angular, AWS, AI', 'Not Eligible'),
('STU130', 'Naveen Kumar', 'Information Technology', 3, 8.72, 'naveen.kumar@campus.edu', 'Cybersecurity, AI, SQL, React', 'Eligible'),
('STU131', 'Megha Sinha', 'Information Technology', 4, 8.25, 'megha.sinha@campus.edu', 'AI, AWS, DevOps, Angular, JavaScript', 'Placed'),
('STU132', 'Raghav Iyer', 'Electronics & Communication', 2, 9.85, 'raghav.iyer@campus.edu', 'VLSI, Verilog, Signal Processing, IoT', 'Not Eligible'),
('STU133', 'Tanisha Dutta', 'Electronics & Communication', 3, 7.46, 'tanisha.dutta@campus.edu', 'Verilog, Signal Processing, Arduino, VLSI, Embedded C', 'Eligible'),
('STU134', 'Siddhant Rao', 'Electronics & Communication', 4, 7.76, 'siddhant.rao@campus.edu', 'Python, VLSI, Embedded C, Signal Processing', 'Eligible'),
('STU135', 'Anushka Verma', 'Electronics & Communication', 4, 8.47, 'anushka.verma@campus.edu', 'Verilog, Arduino, Embedded C, IoT, Python', 'Placed'),
('STU136', 'Kunal Mehra', 'Electronics & Communication', 2, 9.10, 'kunal.mehra@campus.edu', 'Python, Arduino, IoT, MATLAB', 'Not Eligible'),
('STU137', 'Bhavya Shetty', 'Electronics & Communication', 4, 8.58, 'bhavya.shetty@campus.edu', 'VLSI, Embedded C, Signal Processing, Verilog, IoT', 'Placed'),
('STU138', 'Manav Gill', 'Electronics & Communication', 3, 8.22, 'manav.gill@campus.edu', 'Python, IoT, Verilog, VLSI', 'Eligible'),
('STU139', 'Charvi Desai', 'Mechanical Engineering', 3, 6.86, 'charvi.desai@campus.edu', 'Robotics, ANSYS, CATIA, Python', 'Not Eligible'),
('STU140', 'Atharva Joshi', 'Mechanical Engineering', 3, 8.57, 'atharva.joshi@campus.edu', 'AutoCAD, Robotics, MATLAB, Python, SolidWorks', 'Eligible'),
('STU141', 'Nikita Chawla', 'Mechanical Engineering', 4, 7.47, 'nikita.chawla@campus.edu', 'ANSYS, MATLAB, Python, AutoCAD', 'Eligible'),
('STU142', 'Pratik Bose', 'Mechanical Engineering', 3, 9.85, 'pratik.bose@campus.edu', 'SolidWorks, CATIA, AutoCAD, Robotics, MATLAB', 'Eligible'),
('STU143', 'Sneha Raghavan', 'Mechanical Engineering', 3, 8.32, 'sneha.raghavan@campus.edu', 'CATIA, Robotics, ANSYS, AutoCAD, SolidWorks', 'Eligible'),
('STU144', 'Ritesh Yadav', 'Mechanical Engineering', 3, 8.30, 'ritesh.yadav@campus.edu', 'MATLAB, Python, Robotics, SolidWorks, CATIA', 'Eligible'),
('STU145', 'Gauri Phadke', 'Civil Engineering', 4, 8.08, 'gauri.phadke@campus.edu', 'Surveying, MATLAB, Primavera, GIS', 'Eligible'),
('STU146', 'Ayaan Mirza', 'Civil Engineering', 4, 7.47, 'ayaan.mirza@campus.edu', 'AutoCAD, MATLAB, Revit, GIS', 'Eligible'),
('STU147', 'Komal Saini', 'Civil Engineering', 3, 8.45, 'komal.saini@campus.edu', 'MATLAB, STAAD Pro, Primavera, AutoCAD', 'Eligible'),
('STU148', 'Abhishek Pandit', 'Civil Engineering', 4, 7.88, 'abhishek.pandit@campus.edu', 'Revit, Surveying, Primavera, MATLAB, AutoCAD', 'Placed'),
('STU149', 'Ruchi Mathur', 'Civil Engineering', 1, 8.95, 'ruchi.mathur@campus.edu', 'Surveying, Primavera, STAAD Pro, GIS', 'Not Eligible'),
('STU150', 'Vedant Kale', 'Civil Engineering', 4, 7.87, 'vedant.kale@campus.edu', 'MATLAB, STAAD Pro, Primavera, Revit, Surveying', 'Eligible')
ON CONFLICT (student_id) DO NOTHING;
