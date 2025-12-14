import os
import json
import shutil
import random
import asyncio
import streamlit as st
from pathlib import Path
from docx import Document
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_core.prompts import PromptTemplate
import streamlit.components.v1 as components
from langchain_community.vectorstores import FAISS
from streamlit_float import float_init, float_css_helper
from langchain_classic.chains.question_answering.chain import load_qa_chain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# 1. Loading environment variables
load_dotenv()
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
FAISS_INDEX_PATH = "faiss_index"
EMBEDDING_MODEL = "models/embedding-001"
LLM_MODEL = "gemini-2.5-flash"


@st.cache_data(show_spinner=False)
def get_pdf_text(pdf_files):
    """Extracts text from a list of uploaded PDF files."""
    full_text = ""
    for pdf_file in pdf_files:
        pdf = PdfReader(pdf_file)
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text
    return full_text

@st.cache_data(show_spinner=False)
def get_text_contents(file_path):
    """Reads and returns the text content from a given file path."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    
@st.cache_data(show_spinner=False)
def get_word_contents(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)

@st.cache_data(show_spinner=False)
def get_text_chunks(text):
    splitter = RecursiveCharacterTextSplitter(chunk_size=8000, chunk_overlap=2000)
    return splitter.split_text(text)

@st.cache_resource
def get_embeddings():
    """Returns a cached instance of the Google Generative AI Embeddings."""
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=SecretStr(GOOGLE_API_KEY))

@st.cache_resource
def get_llm():
    """Returns a cached instance of the ChatGoogleGenerativeAI model."""
    return ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0.2, google_api_key=SecretStr(GOOGLE_API_KEY or ""))


# ============== Vector Store Functionality =================
def create_and_save_vector_store(sha1_of_username, subject, chapter):
    materials_dir = f"{sha1_of_username}/materials/{subject}/{chapter}"
    FAISS_INDEX_PATH = f"{sha1_of_username}/data/{subject}/{chapter}"
    if os.path.exists(FAISS_INDEX_PATH):
        shutil.rmtree(FAISS_INDEX_PATH)
        st.session_state.vector_store_exists = False
        st.rerun()
    if not os.path.exists(materials_dir) or not os.listdir(materials_dir):
        st.error(f"No materials found for {subject} - {chapter} to create vector store. Please upload files first.")
        st.rerun()
        return None
    all_text = ""
    for file_name in os.listdir(materials_dir):
        file_path = os.path.join(materials_dir, file_name)
        if file_name.lower().endswith(".pdf"):
            with open(file_path, "rb") as pdf_file:
                all_text += get_pdf_text([pdf_file]) + "\n"
        elif file_name.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as text_file:
                all_text += get_text_contents(file_path) + "\n"
        elif file_name.lower().endswith(".docx"):
            with open(file_path, "rb") as word_file:
                all_text += get_word_contents(word_file) + "\n"
        else:
            st.warning(f"Unsupported file format: {file_name}. Skipping.")
    text_chunks = get_text_chunks(all_text)

    # Ensure the target data directory exists (do not delete it)
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)

    # Only remove previous FAISS index files, do NOT remove the subject/chapter directory
    _index_file = os.path.join(FAISS_INDEX_PATH, "faiss.index")
    _pkl_file = os.path.join(FAISS_INDEX_PATH, "faiss.pkl")

    for _file in (_index_file, _pkl_file):
        if os.path.isfile(_file):
            try:
                os.remove(_file)
                st.info(f"Removed previous FAISS file: {os.path.basename(_file)}")
            except Exception as e:
                st.warning(f"Could not remove {os.path.basename(_file)}: {e}")

    vector_store = FAISS.from_texts(text_chunks, embedding=get_embeddings())
    vector_store.save_local(FAISS_INDEX_PATH)
    st.session_state.vector_store_exists = True
    st.rerun()

@st.cache_resource
def load_vector_store(sha1_of_username, subject, chapter):
    """Loads the FAISS vector store from the local path."""
    data_dir = f"{sha1_of_username}/data/{subject}/{chapter}"
    if not os.path.exists(os.path.join(data_dir, "index.faiss")):
        return None

    return FAISS.load_local(
        data_dir, 
        embeddings=get_embeddings(),
        allow_dangerous_deserialization=True
    )



# ================ AI Chat Functionality =================
def get_conversation_chain():
    prompt = """You are an advanced Retrieval-Augmented Generation (RAG) assistant. Your role is to answer user questions naturally by combining retrieved context with your own reasoning and knowledge. Follow these guidelines:
                    ### 🔹 1. Using Context
                    - Never make up information.  
                    - If the context (**{context}**) has relevant details, use them directly in your response.  
                    - When the context is clearly relevant, weave it naturally into your answer and cite it.  
                    - Focus on meaning and intent, not just keyword overlap.  
                    - If the context is only partly useful, combine it with your own knowledge while making it clear which part comes from the context.  
                    - If no helpful context is found, answer naturally without forcing it.  

                    ### 🔹 2. Handling Irrelevant Context
                    - If the context is irrelevant or empty, simply ignore it.  
                    - Don’t shoehorn unrelated context into the answer.  
                    - If the question doesn’t match the context, answer from your knowledge base.  
                    - Never mention whether context exists or not.  

                    ### 🔹 3. Answering Style
                    - Keep the tone clear, human, and conversational.  
                    - Structure answers logically with short paragraphs, bullet points, or lists when needed.  
                    - Stay factual and concise—long only when the question requires it.  
                    - Don’t refuse unless the question is inappropriate or nonsense.  
                    - If uncertain, give the most likely answer based on your knowledge.  
                    - If the question is vague, ask for clarification instead of guessing.  
                    - Absolutely avoid hallucinations—stick to what’s supported by context or common knowledge.  

                    ### 🔹 4. Conversation Flow
                    - Be polite, approachable, and engaging.  
                    - Carry forward relevant details from earlier parts of the conversation.  
                    - Offer smooth follow-ups when the user asks related questions.  

                    ### 🔹 5. Output Format
                    - Always answer in **markdown format**.  
                    - Do not include pre-text or post-text, just the final answer.  

                    ---

                    **Context (if any):**  
                    {context}  

                    **Question:**  
                    {question}  

                    **Answer:**  

    """

    model = get_llm()
    prompt = PromptTemplate(template=prompt, input_variables=['context', 'question'])

    chain = load_qa_chain(model, prompt=prompt, chain_type="stuff")

    return chain

def get_chat_response(user_input, vector_db):
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable is missing.")

    chain = get_conversation_chain()
    docs = vector_db.similarity_search(user_input) if vector_db else []

    if docs:
        response = chain(
            {"input_documents": docs, "question": user_input},
            return_only_outputs=True
        )
        return response.get("output_text", "Sorry, I couldn't find an answer.")
    else:
        response = chain(
            {"input_documents": [], "question": user_input},
            return_only_outputs=True
        )
        return response.get("output_text", "Sorry, I couldn't find an answer.")



# ================= Quiz Functionality =================
def create_question(question_data: dict, idx: int):
    score_increment, question_increment, quiz_end = 0, 0, False
    question_container = st.container(border=True)
    with question_container:
        st.markdown(f"### **Question {idx+1}:** {question_data['question']}")
        user_answer = st.radio(
            "Select your answer:",
            question_data['options'],
            index=None,
            key=f"answer_{idx}"
        )

        _, col1, _, col2, _ = st.columns([1,2,1,2,1])
        with col1:
            if st.button("Submit Answer", key=f"submit_{idx}", disabled=(user_answer is None), use_container_width=True):
                st.session_state.quiz_options_chosen.append(user_answer)
                question_increment = 1

                if user_answer == question_data['correct_option']:
                    score_increment = 1
                    st.success("Correct!", icon="✅")
                else:
                    st.error(f"Incorrect! The correct answer is: **{question_data['correct_option']}**", icon="❌")
        with col2:
            if st.button("End Quiz", key=f"end_{idx}", use_container_width=True):
                quiz_end = True
                # question_increment = -1

    return score_increment, question_increment, quiz_end

def generate_quiz_from_faiss(vector_db, num_questions: int = 5):
    if vector_db is None:
        st.error("Vector database not found. Please upload a PDF first.")
        return []
    
    retrieval_queries = [
        "Generate quiz questions about the key concepts and main ideas in the document.",
        "Create a quiz based on the important details and factual information presented.",
        "Formulate questions that test understanding of the document's primary topics.",
        "What are some potential multiple-choice questions from this text?",
        "Generate a quiz that covers the essential information from the document."
    ]
    retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 20})
    random_query = random.choice(retrieval_queries)
    retrieved_docs = retriever.get_relevant_documents(random_query)

    if len(retrieved_docs) > 15:
        docs_for_context = random.sample(retrieved_docs, 15)
    else:
        docs_for_context = retrieved_docs

    context = " ".join([doc.page_content for doc in docs_for_context])

    quiz_prompt = PromptTemplate(
        input_variables=["context", "num_questions"],
        template="""
        You are an expert quiz generator. Using the provided context, generate {num_questions} multiple-choice questions.
        Introduce variety and randomness in the phrasing of your questions to ensure they are not repetitive.

        Each question must have exactly 4 answer options, and you must clearly specify which option is correct.

         IMPORTANT:
        - Vary the style, structure, and order of your questions so they are not repetitive.
        - Randomize phrasing and avoid predictable patterns.
        - Each question must have exactly 4 answer options.
        - Clearly specify the correct option.
        - Return ONLY valid JSON (no markdown, no extra text).
        - DO NOT indicate option number like 1,2,3,4. Just return the option text.

        Example output format:
        [
          {{
            "question": "Sample question?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "Option A"
          }}
        ]

        Context:
        {context}
        """
    )

    llm = get_llm()
    chain = quiz_prompt | llm
    response = chain.invoke({"context": context, "num_questions": num_questions})

    try:
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "")  # type: ignore
        quiz_data = json.loads(cleaned_response)

        if isinstance(quiz_data, list):
            random.shuffle(quiz_data)
            for question in quiz_data:
                if 'options' in question and isinstance(question['options'], list):
                    random.shuffle(question['options'])
            return quiz_data
        else:
            return []
            
    except Exception as e:
        st.error(f"Failed to create the quiz from the model's response. Please try again. Error: {e}")
        return []



# ================= Flashcards Functionality =================
def generate_flashcards_from_faiss(vector_db, num_flashcards: int = 5):
    if vector_db is None:
        st.error("Vector database not found. Please upload a PDF first.")
        return []
    
    retrieval_queries = [
        "Generate flashcards about the key concepts and main ideas in the document.",
        "Create flashcards based on the important details and factual information presented.",
        "Formulate flashcards that test understanding of the document's primary topics.",
        "What are some potential flashcards from this text?",
        "Generate flashcards that cover the essential information from the document."
    ]
    retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 20})
    random_query = random.choice(retrieval_queries)
    retrieved_docs = retriever.get_relevant_documents(random_query)

    if len(retrieved_docs) > 15:
        docs_for_context = random.sample(retrieved_docs, 15)
    else:
        docs_for_context = retrieved_docs

    context = " ".join([doc.page_content for doc in docs_for_context])

    flashcard_prompt = PromptTemplate(
        input_variables=["context", "num_flashcards"],
        template="""
        You are an expert flashcard generator. Using the provided context, generate {num_flashcards} flashcards.
        Each flashcard should have a question on one side and the answer on the other.

         IMPORTANT:
        - Vary the style, structure, and order of your flashcards so they are not repetitive.
        - Randomize phrasing and avoid predictable patterns.
        - Return ONLY valid JSON (no markdown, no extra text).

        Example output format:
        [
          {{
            "question": "Sample question?",
            "answer": "Sample answer."
          }}
        ]

        Context:
        {context}
        """
    )

    llm = get_llm()
    chain = flashcard_prompt | llm
    response = chain.invoke({"context": context, "num_flashcards": num_flashcards})

    try:
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "") # type: ignore
        flashcard_data = json.loads(cleaned_response)

        if isinstance(flashcard_data, list):
            random.shuffle(flashcard_data)
            return flashcard_data
        else:
            return []
            
    except Exception as e:
        st.error(f"Failed to create the flashcards from the model's response. Please try again. Error: {e}")
        return []



# ================= Mind Map Functionality =================
def generate_mindmap_from_faiss(vector_db):
    """
    Generates a mind map in Mermaid syntax based on the content of a FAISS vector store.
    """
    if vector_db is None:
        st.error("Vector database not found. Please upload and process your materials first.")
        return None

    # Define queries to retrieve broad, summary-level information suitable for a mind map
    retrieval_queries = [
        "Summarize the core topics and key concepts for a mind map.",
        "Extract the main ideas, their sub-points, and hierarchical relationships.",
        "Generate a structured outline of the document's primary themes.",
        "What are the most important concepts and how do they relate to each other?",
        "Create a high-level overview of the material, focusing on structure and key terms."
    ]
    
    # Retrieve relevant documents from the vector store
    retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 20})
    random_query = random.choice(retrieval_queries)
    retrieved_docs = retriever.get_relevant_documents(random_query)

    # Use a sample of the retrieved docs to form the context
    docs_for_context = random.sample(retrieved_docs, min(len(retrieved_docs), 15))
    context = " ".join([doc.page_content for doc in docs_for_context])

    # Create a prompt template that instructs the LLM to generate Mermaid syntax
    mindmap_prompt = PromptTemplate(
        input_variables=["context"],
        template="""
            You are an expert at synthesizing information and creating structured visual summaries.
            Based on the provided context, generate a **mind map** that clearly outlines the key concepts, main topics, and their hierarchical relationships.

            ### STRICT INSTRUCTIONS

            * The output MUST be **valid Mermaid.js `mindmap` syntax**.
            * Start with a single **`root((Main Subject))`** node at the center.
            * Branch out with **main topics/chapters** directly under the root.
            * Add **sub-topics, details, and key points** under their respective parent nodes.
            * The structure MUST remain **hierarchical, expandable, and logically navigable** (avoid flat lists).
            * Keep node text **short, descriptive, and informative**.
            * Do **not** wrap the output in markdown fences (```), JSON, or explanations — return only the raw Mermaid syntax.

            ### Example Output Format:

            ```
            mindmap
            root((Main Topic))
                (Sub-Topic 1)
                (Detail 1.1)
                (Detail 1.2)
                (Sub-Topic 2)
                (Detail 2.1)
                    (Sub-detail 2.1.1)
                (Sub-Topic 3)
            ```

            ### Context for Mind Map Generation:

            {context}
        """
        # template="""
        # You are an expert at synthesizing information and creating visual summaries. 
        # Based on the provided context, generate a mind map that outlines the key concepts, main topics, and their hierarchical relationships.

        # IMPORTANT INSTRUCTIONS:
        # - The output MUST be in valid Mermaid.js mindmap syntax.
        # - Start with a central `root` node representing the main subject.
        # - Branch out from the root with the main ideas or chapters.
        # - Further branch out with sub-topics, key details, or important terms.
        # - KEEP Structure HEIRARCHICAL and navigable.
        # - Keep the text for each node concise and informative.
        # - Return ONLY the raw Mermaid syntax. Do not wrap it in markdown ```mermaid code blocks or provide any explanations.

        # Example output format:
        # mindmap
        #   root((Main Topic))
        #     (Sub-Topic 1)
        #       (Detail 1.1)
        #       (Detail 1.2)
        #     (Sub-Topic 2)
        #       (Detail 2.1)
        #         (Sub-detail 2.1.1)
        #     (Sub-Topic 3)

        # Context to use for mind map generation:
        # {context}
        # """
    )

    # Get the LLM and create the chain
    llm = get_llm()
    chain = mindmap_prompt | llm
    
    try:
        # Invoke the chain and get the response
        response = chain.invoke({"context": context})
        
        # Clean the response content to ensure it's just the Mermaid syntax
        mermaid_syntax = response.content.strip() # type: ignore
        
        if mermaid_syntax.lstrip().startswith("mindmap"):
            return mermaid_syntax
        else:
            st.error("The model returned an invalid format for the mind map. Please try regenerating.")
            return None
            
    except Exception as e:
        st.error(f"An error occurred while generating the mind map: {e}")
        return None


# ===================== Exam Funcationality =====================
def generate_exam_from_faiss(vector_db, total_score: int, num_questions: int = 5):
    if vector_db is None:
        st.error("Vector database not found. Please upload a PDF first.")
        return []
    
    retrieval_queries = [
        "Generate exam questions about the key concepts and main ideas in the document.",
        "Create an exam based on the important details and factual information presented.",
        "Formulate questions that test understanding of the document's primary topics.",
        "Generate an exam that covers the essential information from the document.",
        "What are some potential exam questions from this text?"
    ]
    retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 20})
    random_query = random.choice(retrieval_queries)
    retrieved_docs = retriever.get_relevant_documents(random_query)

    if len(retrieved_docs) > 15:
        docs_for_context = random.sample(retrieved_docs, 15)
    else:
        docs_for_context = retrieved_docs

    context = " ".join([doc.page_content for doc in docs_for_context])

    exam_prompt = PromptTemplate(
        input_variables=["context", "num_questions", "total_score"],
        template="""
        You are an expert exam generator. Using the provided context, generate {num_questions} subjective questions with total marks of {total_score}.
        Introduce variety and randomness in the phrasing of your questions to ensure they are not repetitive.

        Each question must have exactly 1 answer, and answer must be from the provided context.

         IMPORTANT:
        - MUST have exactly 1 answer.
        - Sum of score of all questions must be equal to {total_score}.
        - Each answer must be detailed and to the point.
        - Vary the style, structure, and order of your questions so they are not repetitive.
        - Randomize phrasing and avoid predictable patterns.
        - Return ONLY valid JSON (no markdown, no extra text).

        Example output format:
        [
          {{
            "question": "Sample question?",
            "answer": "Answer text here."
            "score": 1.5
          }}
        ]

        Context:
        {context}
        """
    )

    llm = get_llm()
    chain = exam_prompt | llm
    response = chain.invoke({"context": context, "num_questions": num_questions, "total_score": total_score})

    try:
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "") # type: ignore
        exam_data = json.loads(cleaned_response)

        if isinstance(exam_data, list):
            random.shuffle(exam_data)
            # print(exam_data)
            return exam_data
        else:
            return []
    except Exception as e:
        st.error(f"Failed to create the exam from the model's response. Please try again. Error: {e}")
        return []

def create_exam_question(question:str, idx: int):
    question_increment, exam_end = 0, False
    question_container = st.container(border=True)
    with question_container:
        st.markdown(f"<div style='font-size:24px; font-weight:bold;'>Question {idx+1}: {question}</div>", unsafe_allow_html=True)
        user_answer = st.text_area(
            "Type your answer here:",
            key=f"exam_answer_{idx}"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Submit Answer", key=f"exam_submit_{idx}"):   #, disabled=(not user_answer.strip())
                st.session_state.exam_answers_given.append(user_answer.strip())
                question_increment = 1
        with col2:
            if st.button("End Exam", key=f"exam_end_{idx}"):
                exam_end = True
                question_increment = -1
                
    return question_increment, exam_end

def evaluate_exam(exam_answer, user_answer, marks):
    llm = get_llm()
    prompt = PromptTemplate(
        input_variables=["exam_answer", "user_answer", "marks"],
        template="""
        You are an expert exam evaluator. 
        Given the correct exam answers and the user's answer, calculate the total score. 
        Completely correct answer is worth {marks} points, while you can deduct points for incorrect or partially correct answers.
        If an answer is partially correct, assign partial marks proportionally.
        
        Return only the total score as a float (no text, no explanation).

        Example input:
        Correct answer: The capital of France is Paris.
        User answer: Paris is the capital of France.
        Marks: 5
        
        Example output:
        5.0

        Example input:
        Correct answer: The capital of Britain is London.
        User answer: Paris is the capital of Britain.
        Marks: 5
        
        Example output:
        0
        
        Example input:
        Correct answer: Water boils at 100 degrees Celsius at sea level.
        User answer: Water boils at 90 degrees Celsius.
        Marks: 5

        Example output:
        2.5

        Example input:
        Correct answer: The process by which plants make their own food is called photosynthesis.
        User answer: Plants produce food using sunlight.
        Marks: 5

        Example output:
        3.0

        Input:
        Correct answer: {exam_answer}
        User answer: {user_answer}
        Marks: {marks}

        Output:
        """
    )

    chain = prompt | llm
    response = chain.invoke({
        "exam_answer": exam_answer,
        "user_answer": user_answer,
        "marks": marks
    })

    # print(response)
    try:
        score = float(response.content.strip()) # type: ignore
        return score
    except Exception:
        st.error("Failed to evaluate the exam answers. Please try again.")
        return 0.0



# ================= Chat with AI (general) Functionality =================
def get_chat_response_general(user_input):
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable is missing.")

    model = get_llm()
    response = model.predict(user_input)
    return response

