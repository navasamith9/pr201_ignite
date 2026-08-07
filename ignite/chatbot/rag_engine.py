import os
import re
import requests

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), 'faiss_index')
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

STOPWORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren\'t',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can',
    'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had',
    'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'i',
    'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just', 'me', 'more', 'most', 'my', 'myself', 'no',
    'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out',
    'over', 'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than', 'that', 'the', 'their', 'theirs',
    'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under',
    'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom',
    'why', 'with', 'would', 'you', 'your', 'yours', 'yourself', 'yourselves', 'make', 'give', 'tell', 'show'
}

DOMAIN_KEYWORDS = {
    'iiitdmj', 'iiitdm', 'jabalpur', 'college', 'institute', 'academic', 'cpi', 'spi',
    'grading', 'grade', 'attendance', 'leave', 'branch', 'btech', 'bdes', 'mtech',
    'phd', 'course', 'credit', 'credits', 'registration', 'hostel', 'canteen', 'phc', 'lhtc',
    'admission', 'placement', 'fee', 'tuition', 'senate', 'dugc', 'apcs', 'exam',
    'examination', 'probation', 'termination', 'curriculum', 'backlog', 'rules',
    'guidelines', 'director', 'dean', 'registrar', 'faculty', 'student', 'degree',
    'auditing', 'minor', 'honors', 'punishment', 'dishonesty', 'cheating', 'hall',
    'programme', 'program', 'semester', 'result', 'sgpa', 'cgpa', 'pass', 'fail',
    'library', 'gymkhana', 'sac', 'dasa', 'josaa', 'csab', 'uceed', 'gate', 'ceed',
    'pbi', 'internship', 'thesis', 'ordinance', 'bog', 'dumna', 'khamaria'
}

TYPO_MAP = {
    r'\battendence\b': 'attendance',
    r'\batendance\b': 'attendance',
    r'\batendence\b': 'attendance',
    r'\battandance\b': 'attendance',
    r'\battandence\b': 'attendance',
    r'\bcreadits\b': 'credits',
    r'\bcrdits\b': 'credits',
    r'\bcredt\b': 'credits',
    r'\bcredts\b': 'credits',
    r'\brequirment\b': 'requirement',
    r'\brequirments\b': 'requirements',
    r'\brecquirement\b': 'requirement',
    r'\bpercentge\b': 'percentage',
    r'\bpercantade\b': 'percentage',
    r'\bpct\b': 'percentage',
    r'\bb-tech\b': 'btech',
    r'\bb\s+tech\b': 'btech',
    r'\bcs\b': 'cse',
    r'\bcomputer\s+science\b': 'cse',
}

DETAIL_PATTERNS = [
    r'\bdetail\b', r'\bdetails\b', r'\bdetailed\b', r'\bexplain\b', r'\belaborate\b',
    r'\belaborately\b', r'\bin depth\b', r'\bindepth\b', r'\bfull details\b',
    r'\bmore info\b', r'\bdescribe\b', r'\bthoroughly\b', r'\bfully\b',
]


class RAGEngine:
    def __init__(self):
        self.vectorstore = None
        self.loaded = False
        self._load_vectorstore()

    def _load_vectorstore(self):
        if not os.path.isdir(FAISS_INDEX_DIR):
            print(f"RAGEngine: no FAISS index found at {FAISS_INDEX_DIR}. "
                  f"Run build_vector_index.py to create it.")
            return
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                encode_kwargs={'normalize_embeddings': True},
            )
            self.vectorstore = FAISS.load_local(
                FAISS_INDEX_DIR, embeddings, allow_dangerous_deserialization=True
            )
            self.loaded = True
            print(f"RAGEngine loaded FAISS index with "
                  f"{self.vectorstore.index.ntotal} vectors.")
        except Exception as e:
            print(f"Error loading FAISS index: {e}")

    def normalize_text(self, text):
        t = text.lower()
        for pattern, repl in TYPO_MAP.items():
            t = re.sub(pattern, repl, t)
        return t

    def tokenize(self, text):
        norm = self.normalize_text(text)
        return [w for w in re.findall(r'\b[a-zA-Z0-9]{2,}\b', norm)]

    def extract_keywords(self, text):
        tokens = self.tokenize(text)
        return [t for t in tokens if t not in STOPWORDS]

    def wants_detail(self, query):
        q = query.lower()
        return any(re.search(p, q) for p in DETAIL_PATTERNS)

    def _get_direct_intent_answer(self, query):
        q = self.normalize_text(query)
        keywords = set(self.extract_keywords(query))

        # Intent 1: Attendance requirement
        if ('attendance' in keywords or 'attend' in q) and any(w in keywords or w in q for w in ['minimum', 'percentage', 'required', 'requirement', 'criteria', 'rules', 'policy']):
            return {
                "answer": "The minimum required attendance policy at IIITDMJ is:\n\n"
                          "• **75% mandatory attendance** of total scheduled classes (lectures, tutorials, and labs combined) for each subject individually.\n"
                          "• **60% minimum attendance** criterion applies for final year students.\n"
                          "• **Up to 60%** attendance relaxation may be permitted by the Senate Chairperson on valid medical grounds involving prolonged hospitalization.\n"
                          "• **Up to 50%** attendance waiver is available for students running registered startups through the institute incubation cell.",
                "source": "Academic Guidelines UG (Dec 2025) - Section 8.1"
            }

        # Intent 2: Minimum Credits for B.Tech CSE Degree
        if ('credit' in keywords or 'credits' in keywords) and ('cse' in q or 'computer science' in q) and any(w in keywords or w in q for w in ['minimum', 'number', 'required', 'complete', 'total', 'degree', 'btech']):
            return {
                "answer": "To complete the B.Tech degree in Computer Science & Engineering (CSE) at IIITDMJ:\n\n"
                          "• You must earn a minimum of **156 to 160 credits** (typically **160 total credits** across 8 semesters as prescribed in the Senate-approved curriculum).\n"
                          "• A minimum of **120 credits** must be completed till the 6th semester to be eligible for a Project-Based Internship (PBI).",
                "source": "Academic Guidelines UG (Dec 2025) - Section 9.2"
            }

        # Intent 3: General B.Tech / B.Des Minimum Credits
        if ('credit' in keywords or 'credits' in keywords) and any(w in keywords or w in q for w in ['minimum', 'number', 'required', 'complete', 'total', 'degree', 'btech', 'bdes', 'program']):
            return {
                "answer": "Minimum credit requirements for undergraduate programmes at IIITDMJ are:\n\n"
                          "• **B.Tech (CSE, ECE, ME, SM):** Minimum 156 to 160 total credits across 8 semesters.\n"
                          "• **B.Des:** Minimum 150 to 160 total credits across 8 semesters.\n"
                          "• **Project-Based Internship (PBI):** Minimum 120 credits completed till 6th semester.\n"
                          "• **Minor Degree:** 13 to 17 additional credits (5 courses + 1 project).",
                "source": "Academic Guidelines UG (Dec 2025) - Section 9.2"
            }

        # Intent 4: Minimum CPI for Graduation / Degree
        if ('cpi' in keywords or 'cgpa' in q) and any(w in keywords or w in q for w in ['minimum', 'required', 'graduation', 'degree', 'award', 'pass']):
            return {
                "answer": "The minimum CPI (Cumulative Performance Index) required for the award of a B.Tech / B.Des degree at IIITDMJ is **5.0**.",
                "source": "Academic Guidelines UG (Dec 2025) - Section 10.2"
            }

        # Intent 5: Branch Change Policy
        if ('branch' in keywords or 'discipline' in keywords) and any(w in keywords or w in q for w in ['change', 'switch', 'transfer', 'process', 'rules']):
            return {
                "answer": "Branch change for B.Tech students at IIITDMJ takes place at the end of the 2nd semester (1st year). Key guidelines:\n\n"
                          "• **Minimum CPI:** Must have a minimum CPI of **8.0** (or be in the top 5 students of the entire batch).\n"
                          "• **Academic Record:** Must have completed all 1st-year registered courses without any backlog or disciplinary action.\n"
                          "• **Capacity:** Branch strength cannot exceed 10% above sanctioned capacity or drop below 85%.",
                "source": "Academic Guidelines UG (Dec 2025) - Section 16"
            }

        # Intent 6: Program Duration
        if any(w in keywords or w in q for w in ['duration', 'length', 'years', 'semesters']) and any(w in keywords or w in q for w in ['btech', 'bdes', 'program', 'degree', 'complete']):
            return {
                "answer": "The duration guidelines for undergraduate programmes at IIITDMJ are:\n\n"
                          "• **Normal Duration:** 8 regular semesters (4 years).\n"
                          "• **Fast-Track Exit:** Meritorious students earning extra credits can complete in **7 regular semesters (3.5 years)**.\n"
                          "• **Maximum Permitted Duration:** 6 years to complete the degree.",
                "source": "Academic Guidelines UG (Dec 2025) - Section 10.3"
            }

        # Intent 7: Extra Credits Policy
        if ('credit' in keywords or 'credits' in keywords) and any(w in keywords or w in q for w in ['extra', 'additional', 'overload']):
            return {
                "answer": "Extra Credits Policy at IIITDMJ:\n\n"
                          "• A student can register for a maximum of **7 additional credits** per regular semester over and above the normal load.\n"
                          "• Extra credits allow students to clear backlogs, pursue a minor degree, or fast-track graduation in 7 semesters.",
                "source": "Academic Guidelines UG (Dec 2025) - Section 7.3"
            }

        # Intent 7b: Leave Policy (casual / medical)
        if ('leave' in keywords or 'leaves' in keywords) and any(w in keywords or w in q for w in ['medical', 'casual', 'avail', 'days', 'how many', 'maximum']):
            return {
                "answer": "Leave Policy at IIITDMJ:\n\n"
                          "• **Casual Leave:** A student can avail a maximum of **7 days** casual leave on valid reason.\n"
                          "• **Medical Leave:** A student can avail a maximum of **15 days** leave on medical grounds in a semester.",
                "source": "Academic Guidelines UG (Dec 2025)"
            }

        # Intent 8: Hostel & Facilities
        if any(w in keywords or w in q for w in ['hostel', 'facilities', 'residence', 'campus']):
            return {
                "answer": "IIITDMJ Campus & Hostel Facilities:\n\n"
                          "• **Halls of Residence:** Hall 1, Hall 3, Hall 4 (for male students), and Mother Teresa Hall (for female students).\n"
                          "• **Academic & Tech:** Lecture Hall Teaching Complex (LHTC), Central Library, and Computer Center.\n"
                          "• **Amenities:** Primary Health Centre (PHC) with 24/7 medical care, Student Activity Centre (SAC), Gymkhana, and Canteen.",
                "source": "IIITDMJ Official Website (iiitdmj.ac.in)"
            }

        # Intent 9: Director & Contact
        if any(w in keywords or w in q for w in ['director', 'contact', 'address', 'location', 'phone', 'email']):
            return {
                "answer": "IIITDM Jabalpur Contact Information:\n\n"
                          "• **Director:** Prof. Bhartendu K. Singh.\n"
                          "• **Address:** PDPM IIITDM Jabalpur, Dumna Airport Road, P.O. Khamaria, Jabalpur - 482005, MP, India.\n"
                          "• **Phone:** +91-761-2632044 | **Email:** registry@iiitdmj.ac.in.",
                "source": "IIITDMJ Official Website (iiitdmj.ac.in)"
            }

        # Intent 10: Placements
        if any(w in keywords or w in q for w in ['placement', 'placements', 'jobs', 'recruitment', 'internship']):
            return {
                "answer": "Placement Cell at IIITDMJ:\n\n"
                          "• IIITDMJ has an active Placement Cell coordinating campus recruitment and Project-Based Internships (PBI).\n"
                          "• Top recruiters include major IT, software, core engineering, and design companies.\n"
                          "• Students in 7th/8th semester can opt for a 12-credit Project-Based Internship (PBI) in industry or research organizations.",
                "source": "IIITDMJ Official Website (iiitdmj.ac.in)"
            }

        return None

    def is_in_context(self, query, top_chunks):
        query_kw = self.extract_keywords(query)
        if not query_kw:
            return False

        if not top_chunks:
            return False

        has_domain_keyword = any(kw in DOMAIN_KEYWORDS for kw in query_kw)

        top_chunk, top_score = top_chunks[0]

        # Cross-check with a plain keyword overlap against the top chunk so a
        # semantically "close" but factually unrelated match (e.g. a shared
        # surname) can't sneak through purely on vector similarity.
        content_tokens = set(self.tokenize(top_chunk['content'] + " " + top_chunk.get('section', '')))
        raw_matches = sum(1 for kw in query_kw if kw in content_tokens)
        match_ratio = raw_matches / float(len(query_kw))

        if has_domain_keyword:
            return top_score >= 0.38
        return top_score >= 0.48 and match_ratio >= 0.34

    def retrieve(self, query, k=5):
        if not self.vectorstore:
            return []

        results = self.vectorstore.similarity_search_with_score(query, k=k)
        scored_chunks = []
        for doc, l2_distance in results:
            # Embeddings are normalized (unit vectors), so for squared L2 distance:
            # cosine_similarity = 1 - (l2_distance / 2). Clip for numerical safety.
            similarity = max(0.0, min(1.0, 1.0 - (l2_distance / 2.0)))
            chunk = {
                'content': doc.page_content,
                'source': doc.metadata.get('source', ''),
                'section': doc.metadata.get('section', ''),
                'url': doc.metadata.get('url', ''),
                'page': doc.metadata.get('page', ''),
            }
            scored_chunks.append((chunk, similarity))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks

    def answer_query(self, query):
        query_clean = query.strip()
        if not query_clean:
            return {
                "answer": "Please enter a valid question.",
                "source": "System",
                "in_context": False
            }

        detailed = self.wants_detail(query_clean)

        # Check direct curated academic intents first for 100% crispness & accuracy
        direct_result = self._get_direct_intent_answer(query_clean)
        if direct_result:
            answer = direct_result["answer"]
            if detailed:
                top_chunks = self.retrieve(query_clean)
                if top_chunks:
                    extra = self.clean_fallback_snippet(top_chunks[0][0]['content'], max_len=800)
                    answer = f"{answer}\n\nMore detail:\n{extra}"
            return {
                "answer": answer,
                "source": direct_result["source"],
                "in_context": True,
                "context_used": direct_result["answer"]
            }

        top_chunks = self.retrieve(query_clean)
        in_ctx = self.is_in_context(query_clean, top_chunks)

        if not in_ctx:
            return {
                "answer": "I couldn't find anything about that in IIITDMJ's academic guidelines or the official website. Try asking about admissions, academics, attendance, credits, hostel, placements, or contact info.",
                "source": "Out of Context Guardrail",
                "in_context": False
            }

        retrieved_contexts = []
        sources = set()
        for chunk, s in top_chunks[:3]:
            retrieved_contexts.append(f"[{chunk['source']} - {chunk['section']}]: {chunk['content']}")
            sources.add(chunk['source'])

        context_str = "\n\n".join(retrieved_contexts)
        primary_source = " | ".join(sources)

        # Attempt Ollama generation with fast options
        ollama_answer = self._call_ollama(query_clean, context_str, detailed)
        if ollama_answer:
            return {
                "answer": ollama_answer,
                "source": primary_source,
                "in_context": True,
                "context_used": context_str
            }

        # Clean fallback without Annexure preamble
        top_chunk = top_chunks[0][0]
        max_len = 800 if detailed else 280
        content_snippet = self.clean_fallback_snippet(top_chunk['content'], max_len=max_len)

        return {
            "answer": content_snippet,
            "source": primary_source,
            "in_context": True,
            "context_used": context_str
        }

    def clean_fallback_snippet(self, text, max_len=280):
        # Remove raw section numbers like 10.1.1., 9.2.1, page numbers
        cleaned = re.sub(r'\b\d+\.\d+(\.\d+)*\.?\s*', '', text)
        cleaned = re.sub(r'According to Annexure II.*?:', '', cleaned)
        cleaned = re.sub(r'Academic Guidelines UG - Page \d+', '', cleaned)
        cleaned = ' '.join(cleaned.split())

        # Drop a leading fragment left over from a mid-sentence chunk boundary
        # (e.g. "authorities. Following leaves are..." -> starts with a stray
        # word + period before the real first sentence).
        if cleaned and cleaned[0].islower():
            first_break = cleaned.find('. ')
            if 0 < first_break < 80:
                cleaned = cleaned[first_break + 2:]

        if len(cleaned) <= max_len:
            return cleaned

        truncated = cleaned[:max_len]
        # cut at the last sentence boundary, or failing that the last space, so we never chop mid-word
        last_boundary = max(truncated.rfind('. '), truncated.rfind('? '), truncated.rfind('! '))
        if last_boundary > max_len * 0.4:
            return truncated[:last_boundary + 1]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated.rstrip('.,;: ') + '.'

    def _call_ollama(self, query, context, detailed=False):
        shared_rules = (
            'The context may be cut off mid-sentence at its start or end (chunk boundaries) — ignore any '
            'stray partial fragment and never copy the context verbatim; always rewrite the answer yourself '
            'in your own complete, grammatical sentences.'
        )
        if detailed:
            instruction = (
                'Answer the question accurately and fully based strictly on the provided context. '
                'Do NOT include phrases like "According to the context", "Based on Annexure", or section/page numbers. '
                f'{shared_rules} '
                'Give a clear, well-structured explanation (a short paragraph plus bullet points where helpful), '
                'covering all relevant details from the context.'
            )
            num_predict = 400
        else:
            instruction = (
                'Answer the question crisp, direct, pinpointed, and accurately based strictly on the provided context. '
                'Do NOT include phrases like "According to the context", "Based on Annexure", or section/page numbers. '
                f'{shared_rules} '
                'Give a direct answer in 1-3 short bullet points or one short sentence. Do not elaborate further than necessary.'
            )
            num_predict = 150

        prompt = f"""System: You are the official AI assistant for IIITDM Jabalpur (IIITDMJ). {instruction}

Context:
{context}

Question: {query}

Answer:"""

        try:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 1024,
                    "num_predict": num_predict
                }
            }
            resp = requests.post(url, json=payload, timeout=6.0)
            if resp.status_code == 200:
                res = resp.json().get("response", "")
                if res and len(res.strip()) > 5:
                    clean_res = res.strip()
                    # Clean out preamble if model outputs it
                    clean_res = re.sub(r'^(According to|Based on).*?:\s*', '', clean_res, flags=re.IGNORECASE)
                    return clean_res
        except Exception as e:
            print(f"Ollama API note: {e}")
            
        return None

rag_engine = RAGEngine()

