// Mock student dataset as specified in plan.md Section 5.A
const MOCK_STUDENTS = [
  {
    student_id: "STU-2024-101",
    name: "Aarav Sharma",
    department: "Computer Science (CSE)",
    year: 4,
    cgpa: 9.42,
    email: "aarav.sharma@campus.edu",
    skills: ["Python", "Docker", "PyTorch", "Kubernetes"],
    placement_status: "Placed (Tier 1)"
  },
  {
    student_id: "STU-2024-102",
    name: "Rhea Sen",
    department: "Computer Science (CSE)",
    year: 4,
    cgpa: 8.95,
    email: "rhea.sen@campus.edu",
    skills: ["React", "FastAPI", "PostgreSQL", "Node.js"],
    placement_status: "Placed (Tier 1)"
  },
  {
    student_id: "STU-2024-103",
    name: "Vikram Malhotra",
    department: "Electronics & Comm (ECE)",
    year: 4,
    cgpa: 8.78,
    email: "vikram.m@campus.edu",
    skills: ["Embedded C", "Rust", "VLSI", "Linux"],
    placement_status: "Eligible"
  },
  {
    student_id: "STU-2024-104",
    name: "Ananya Iyer",
    department: "Information Tech (IT)",
    year: 3,
    cgpa: 9.15,
    email: "ananya.i@campus.edu",
    skills: ["Go", "Distributed Systems", "SQL", "Cloud"],
    placement_status: "Eligible"
  },
  {
    student_id: "STU-2024-105",
    name: "Karan Patel",
    department: "Mechanical Eng (ME)",
    year: 4,
    cgpa: 7.90,
    email: "karan.p@campus.edu",
    skills: ["SolidWorks", "MATLAB", "Python", "Data Analysis"],
    placement_status: "Placed (Core)"
  },
  {
    student_id: "STU-2024-106",
    name: "Tanvi Gupta",
    department: "Computer Science (CSE)",
    year: 4,
    cgpa: 8.65,
    email: "tanvi.g@campus.edu",
    skills: ["Next.js", "Tailwind", "GraphQL", "MongoDB"],
    placement_status: "Eligible"
  },
  {
    student_id: "STU-2024-107",
    name: "Aditya Verma",
    department: "Computer Science (CSE)",
    year: 3,
    cgpa: 9.60,
    email: "aditya.v@campus.edu",
    skills: ["C++", "Algorithms", "CUDA", "Linux Kernel"],
    placement_status: "Eligible"
  }
];

// Realistic mock responses for standard demo queries
function getMockResponse(query) {
  const q = query.toLowerCase();

  if (q.includes("above 8.5") || q.includes("> 8.5") || q.includes("8.5")) {
    const matches = MOCK_STUDENTS.filter(s => s.cgpa > 8.5);
    return {
      success: true,
      query: "SELECT student_id, name, department, year, cgpa, placement_status FROM students WHERE cgpa > 8.5 ORDER BY cgpa DESC;",
      latency_ms: 142,
      summary: `Found **${matches.length} students** with CGPA above 8.5 in the university database.`,
      students: matches
    };
  }

  if (q.includes("highest") || q.includes("topper")) {
    const highest = [...MOCK_STUDENTS].sort((a, b) => b.cgpa - a.cgpa).slice(0, 1);
    return {
      success: true,
      query: "SELECT * FROM students ORDER BY cgpa DESC LIMIT 1;",
      latency_ms: 98,
      summary: `The student with the highest CGPA is **${highest[0].name}** with a CGPA of **${highest[0].cgpa}**.`,
      students: highest
    };
  }

  if (q.includes("placement") || q.includes("eligible")) {
    const matches = MOCK_STUDENTS.filter(s => s.placement_status.includes("Eligible") || s.placement_status.includes("Placed"));
    return {
      success: true,
      query: "SELECT * FROM students WHERE placement_status LIKE '%Eligible%' OR placement_status LIKE '%Placed%';",
      latency_ms: 185,
      summary: `Found **${matches.length} students** eligible or active in the university placement drive.`,
      students: matches
    };
  }

  if (q.includes("cse") || q.includes("computer science")) {
    const matches = MOCK_STUDENTS.filter(s => s.department.includes("CSE"));
    return {
      success: true,
      query: "SELECT * FROM students WHERE department LIKE '%CSE%';",
      latency_ms: 120,
      summary: `Found **${matches.length} students** enrolled in the Department of Computer Science.`,
      students: matches
    };
  }

  if (q.includes("above 9") || q.includes("> 9")) {
    const matches = MOCK_STUDENTS.filter(s => s.cgpa >= 9.0);
    return {
      success: true,
      query: "SELECT COUNT(*), AVG(cgpa) FROM students WHERE cgpa >= 9.0;",
      latency_ms: 110,
      summary: `There are **${matches.length} students** holding an exceptional CGPA of 9.0 or higher.`,
      students: matches
    };
  }

  // Default fallback mock response
  return {
    success: true,
    query: `SELECT * FROM students WHERE name ILIKE '%${query.trim()}%' OR skills::text ILIKE '%${query.trim()}%';`,
    latency_ms: 160,
    summary: `Retrieved records matching query: "${query}"`,
    students: MOCK_STUDENTS.slice(0, 3)
  };
}

if (typeof window !== 'undefined') {
  window.MOCK_STUDENTS = MOCK_STUDENTS;
  window.getMockResponse = getMockResponse;
}

