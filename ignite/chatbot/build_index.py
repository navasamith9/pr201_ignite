import os
import re
import json
import requests
from bs4 import BeautifulSoup
import pypdf

PDF_PATH = r"c:\Users\rajes\OneDrive\Desktop\ignite_final\2944 Annexure II _ Academic Guidelines_UG modified Dec 2025_.pdf"
OUTPUT_JSON = r"c:\Users\rajes\OneDrive\Desktop\ignite_final\pr201_ignite\ignite\chatbot\iiitdmj_rag_data.json"

def extract_pdf_chunks(pdf_path):
    print("Extracting text from Annexure PDF...")
    reader = pypdf.PdfReader(pdf_path)
    chunks = []
    
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text or not text.strip():
            continue

        page_num = page_idx + 1
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        page_text = " ".join(lines)
        page_text = " ".join(page_text.split())

        # Split into sentences first so chunks never start/end mid-sentence.
        sentences = re.split(r'(?<=[.!?])\s+', page_text)

        current_chunk = []
        current_word_count = 0

        def flush_chunk():
            if not current_chunk:
                return
            chunk_text = " ".join(current_chunk).strip()
            if len(chunk_text) > 30:
                chunks.append({
                    "id": f"pdf_p{page_num}_{len(chunks)+1}",
                    "source": "Annexure II (Academic Guidelines UG Dec 2025)",
                    "section": f"Academic Guidelines UG - Page {page_num}",
                    "page": page_num,
                    "content": chunk_text
                })

        for sentence in sentences:
            if not sentence.strip():
                continue
            current_chunk.append(sentence)
            current_word_count += len(sentence.split())

            if current_word_count >= 200:
                flush_chunk()
                current_chunk = []
                current_word_count = 0

        flush_chunk()
            
    print(f"Extracted {len(chunks)} PDF chunks.")
    return chunks

def crawl_website():
    print("Crawling IIITDMJ official website (https://www.iiitdmj.ac.in)...")
    urls_to_crawl = [
        ("Home & Overview", "https://www.iiitdmj.ac.in"),
        ("About IIITDMJ", "https://www.iiitdmj.ac.in/about.php"),
        ("Academics", "https://www.iiitdmj.ac.in/academics/academics.php"),
        ("Admissions", "https://www.iiitdmj.ac.in/academics/admission.php"),
        ("Administration", "https://www.iiitdmj.ac.in/administration/overview.php"),
        ("Placement Cell", "https://www.iiitdmj.ac.in/placement.php"),
        ("Campus Life & Hostels", "https://www.iiitdmj.ac.in/campuslife/overview.php"),
        ("Computer Center", "https://www.iiitdmj.ac.in/cc.php"),
        ("Library", "https://www.iiitdmj.ac.in/library.php"),
        ("Contact & Location", "https://www.iiitdmj.ac.in/contact.php"),
    ]
    
    web_chunks = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for title, url in urls_to_crawl:
        try:
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for s in soup(["script", "style", "nav", "footer"]):
                    s.decompose()
                
                text = soup.get_text(separator=' ')
                clean_text = ' '.join(text.split())
                
                words = clean_text.split()
                chunk_size = 150
                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i+chunk_size]
                    if len(chunk_words) > 25:
                        web_chunks.append({
                            "id": f"web_{len(web_chunks)+1}",
                            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
                            "section": f"Website - {title}",
                            "url": url,
                            "content": " ".join(chunk_words)
                        })
        except Exception as e:
            print(f"Web crawl note for {url}: {e}")
            
    # Key structured data fallback for high accuracy
    structured_web_info = [
        {
            "id": "struct_1",
            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
            "section": "Website - About IIITDMJ",
            "url": "https://www.iiitdmj.ac.in",
            "content": "PDPM Indian Institute of Information Technology, Design and Manufacturing Jabalpur (IIITDMJ) is an Institute of National Importance established in 2005 by the Ministry of Education, Government of India. It focuses on IT-enabled Design and Manufacturing education and research. Located at Dumna Airport Road, P.O. Khamaria, Jabalpur - 482005, MP, India. The current Director is Prof. Bhartendu K. Singh."
        },
        {
            "id": "struct_2",
            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
            "section": "Website - Programmes Offered",
            "url": "https://www.iiitdmj.ac.in/academics/",
            "content": "IIITDM Jabalpur offers B.Tech in Computer Science & Engineering (CSE), Electronics & Communication Engineering (ECE), Mechanical Engineering (ME), and Smart Manufacturing (SM); Bachelor of Design (B.Des.); M.Tech, M.Des, and Ph.D. programmes."
        },
        {
            "id": "struct_3",
            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
            "section": "Website - Admissions",
            "url": "https://www.iiitdmj.ac.in/academics/admission.php",
            "content": "Undergraduate B.Tech admissions are based on JEE Main ranks through JoSAA/CSAB counselling. B.Des admissions are based on UCEED scores. International students are admitted via DASA. M.Tech admissions are via GATE/CCMT and M.Des via CEED."
        },
        {
            "id": "struct_4",
            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
            "section": "Website - Campus Facilities",
            "url": "https://www.iiitdmj.ac.in",
            "content": "IIITDMJ facilities include Lecture Hall Teaching Complex (LHTC), Central Library, Computer Center, Primary Health Centre (PHC), Hall of Residence 1, Hall of Residence 3, Hall of Residence 4, Mother Teresa Hall, Gymkhana, and Canteen."
        },
        {
            "id": "struct_5",
            "source": "IIITDMJ Official Website (iiitdmj.ac.in)",
            "section": "Website - Contact Info",
            "url": "https://www.iiitdmj.ac.in/contact.php",
            "content": "Address: PDPM IIITDM Jabalpur, Dumna Airport Road, P.O. Khamaria, Jabalpur - 482005, Madhya Pradesh, India. Phone: +91-761-2632044. Email: registry@iiitdmj.ac.in."
        },
        {
            "id": "struct_6",
            "source": "Academic Guidelines UG (Dec 2025)",
            "section": "Academic Guidelines - Attendance Rules",
            "url": "https://www.iiitdmj.ac.in/academics/",
            "content": "Attendance Rules at IIITDMJ: Attendance of 75% of total scheduled classes is mandatory in all subjects individually for regular students. For final year students, the minimum attendance criterion is 60%. In exceptional medical cases (prolonged hospitalization), attendance up to 60% may be permitted by the Senate Chairperson. Students running registered startups through institute incubation cell may get an attendance waiver of up to 50%."
        },
        {
            "id": "struct_7",
            "source": "Academic Guidelines UG (Dec 2025)",
            "section": "Academic Guidelines - Minimum Credits Requirement",
            "url": "https://www.iiitdmj.ac.in/academics/",
            "content": "Minimum Credits Requirements for B.Tech & UG Degrees: Completing B.Tech CSE (Computer Science & Engineering) degree requires earning a minimum of 156 to 160 credits across 8 semesters as per Senate approved curriculum (typically 160 credits). B.Tech ECE, ME, and SM also require 156-160 credits. B.Des requires 150-160 credits. For Project-Based Internship (PBI), students must complete minimum 120 credits till VI semester. A Minor degree requires 13 to 17 credits."
        },
        {
            "id": "struct_8",
            "source": "Academic Guidelines UG (Dec 2025)",
            "section": "Academic Guidelines - Minimum CPI & Duration",
            "url": "https://www.iiitdmj.ac.in/academics/",
            "content": "Graduation Requirements & Duration: Minimum CPI required for award of B.Tech / B.Des degree is 5.0. Minimum duration is 8 regular semesters (4 years), but meritorious students earning extra credits can complete in 7 semesters (3.5 years). Maximum permitted duration is 6 years."
        },
        {
            "id": "struct_9",
            "source": "Academic Guidelines UG (Dec 2025)",
            "section": "Academic Guidelines - Branch Change Policy",
            "url": "https://www.iiitdmj.ac.in/academics/",
            "content": "Branch Change Rules for B.Tech: Allowed at the end of the 2nd semester (1st year). Requires a minimum CPI of 8.0 or being among top 5 students in the batch, with no backlog courses and no disciplinary action."
        }
    ]
    web_chunks.extend(structured_web_info)
    return web_chunks

if __name__ == "__main__":
    pdf_chunks = extract_pdf_chunks(PDF_PATH)
    web_chunks = crawl_website()
    all_chunks = web_chunks + pdf_chunks
    
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
        
    print(f"Saved {len(all_chunks)} total chunks to {OUTPUT_JSON}")
