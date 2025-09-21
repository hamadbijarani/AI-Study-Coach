import os
import time
from backend import *
import streamlit as st
from ai_features import *
import streamlit.components.v1 as components

# ================ Home Page Functionality =================
def home_page():
    st.header("🏠 Home")
    st.info("Welcome to AI Study Assistant! Create subjects, upload materials, and test yourself with AI-powered feedback.")

    if not st.session_state.app_layout == "wide":
        st.session_state.app_layout = "wide"
        st.rerun()
    
    # ===== Subjects & Chapters =====
    subjects = get_subjects(st.session_state.sha1_of_username)
    
    if subjects:
        st.write("Click on any subject to view details:")
        
        # Create columns for better layout
        cols = st.columns(len(subjects)+2, gap="large")
        
        for i, subject in enumerate(subjects):
            with cols[(i % len(subjects))+1]:
                if st.button(f"📖 {subject}", key=f"subject_{i}", use_container_width=True):
                    st.session_state.selected_subject = subject
                    st.rerun()
                
        
        # Show selected subject details
        if st.session_state.selected_subject:
            st.subheader(f"📚 {st.session_state.selected_subject}")
            chapters = get_chapters(st.session_state.sha1_of_username, st.session_state.selected_subject)
            if chapters:
                selected_chapter = st.radio("Select a chapter:", chapters, key=f"{st.session_state.selected_subject}_chapters")
                
                if st.button("Open the chapter"):
                    st.session_state.selected_chapter = selected_chapter
                    st.session_state.page = "📖 Open a chapter"
                    st.rerun()
            else:
                st.info("No chapters found for this subject.")
        else:
            st.info("Select a subject to view its chapters.")
            
    else:
        st.info("No subjects found.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.container(border=True):
            if not st.session_state.add_chap_clicked:
                if st.button("Add Chapter"):
                    st.session_state.add_chap_clicked = True
                    st.rerun()
            else:
                st.subheader("Add a new chapter")
                chapter_name = st.text_input("Enter chapter name:")
                _, ccol1, _, ccol2, _ = st.columns([1, 1, 1, 1, 1])
                with ccol1:
                    if st.button("Add Chapter", key="add_chap") and chapter_name:
                        if st.session_state.selected_subject is None:
                            st.error("Please select a subject first.")
                            time.sleep(1)
                            st.session_state.add_chap_clicked = False
                            st.rerun()
                        add_chapter(st.session_state.sha1_of_username, st.session_state.selected_subject, chapter_name)
                        st.session_state.add_chap_clicked = False
                        st.rerun()
                with ccol2:
                    if st.button("Cancel", key="cancel_chap"):
                        st.session_state.add_chap_clicked = False
                        st.rerun()
    with col2:
        with st.container(border=True):
            if not st.session_state.add_subj_clicked:
                if st.button("Add Subject"):
                    st.session_state.add_subj_clicked = True
                    st.rerun()
            else:
                st.subheader("Add a new Subject")
                subject_name = st.text_input("Enter subject name:")
                _, scol1, _, scol2, _ = st.columns([1, 1, 1, 1, 1])
                with scol1:
                    if st.button("Add Subject", key="add_subj") and subject_name:
                        print(add_subject(st.session_state.sha1_of_username, subject_name))
                        st.session_state.add_subj_clicked = False
                        st.rerun()
                with scol2:
                    if st.button("Cancel", key="cancel_subj"):
                        st.session_state.add_subj_clicked = False
                        st.rerun()


# ================ chapter functionality ====================
def chat_with_ai_about_chapter(subject, chapter):
    vector_score = load_vector_store(st.session_state.sha1_of_username, subject, chapter)
    if st.session_state.chat_history.__len__() > 20:
        st.session_state.chat_history = st.session_state.chat_history[-20:]
        
    chat_container = st.container(width=900, height=500, border=True)
    with chat_container:
        conv_container = st.container(width=900, height=400, border=False)
        with conv_container:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.chat_message("user").markdown(message["content"])
                else:
                    st.chat_message("assistant").markdown(message["content"])
        prompt = st.chat_input("Ask anything about this chapter...")
        if prompt:
            with conv_container:
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                st.chat_message("user").markdown(prompt)

                with st.spinner("AI is typing..."):
                    response = get_chat_response(prompt, vector_score)
                    # response = "Response from AI based on the chapter content."
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    st.chat_message("assistant").markdown(response)

def quiz_on_chapter(subject, chapter):
    vector_store = load_vector_store(st.session_state.sha1_of_username, subject, chapter)

    if not st.session_state.quiz_ongoing:
        st.radio("How many questions would you like in the quiz?", [5, 10, 20], key="quiz_total_questions", horizontal=True)
        if st.button("Start Quiz"):
            with st.spinner("Generating quiz..."):
                st.session_state.quiz_question_bank = generate_quiz_from_faiss(vector_store, st.session_state.quiz_total_questions)
            if st.session_state.quiz_question_bank:
                st.session_state.quiz_ongoing = True
                st.session_state.quiz_score = 0
                st.session_state.quiz_question_number = 0
                st.session_state.quiz_ended = False
                st.session_state.quiz_options_chosen = []
                st.session_state.quiz_balloons = False
                st.session_state.quiz_review_mode = False
                st.session_state.record_added = False
                st.session_state.completed = True
                st.rerun()
            else:
                st.error("Could not generate a quiz. Please check your document or try again.")
    else:
        q_idx = st.session_state.quiz_question_number
        total_qs = len(st.session_state.quiz_question_bank)
        if  q_idx < total_qs and not st.session_state.quiz_ended:
            current_question = st.session_state.quiz_question_bank[q_idx]
            score_inc, ques_inc, quiz_end = create_question(current_question, q_idx)
            if ques_inc > 0:
                st.session_state.quiz_score += score_inc
                st.session_state.quiz_question_number += ques_inc
                st.rerun()
            if quiz_end:
                st.session_state.quiz_ended = True
                st.session_state.quiz_question_number -= ques_inc
                st.session_state.completed = False
                st.rerun()
        else:
            st.session_state.quiz_ended = True
            if st.session_state.quiz_balloons == False:
                if st.session_state.quiz_score > 0:
                    st.balloons()
                st.session_state.quiz_balloons = True
            st.markdown(f"## Quiz Complete! Your Score: \
                        {st.session_state.quiz_score} / {st.session_state.quiz_question_bank.__len__()}")
            _,col1, _, col2,_ = st.columns([1,1,1,1,1])
            with col1:
                if st.button("End Quiz", use_container_width=True):
                    st.session_state.quiz_ongoing = False
                    st.rerun()
            with col2:
                if st.button("Review Answers", use_container_width=True):
                    st.session_state.quiz_review_mode = True
                    st.rerun()

            if st.session_state.quiz_review_mode:
                with st.container(height=500, border=True):
                    st.button("Close Review", on_click=lambda: st.session_state.update({"quiz_review_mode": False}))
                    st.markdown("### 🧐 Review Your Answers")
                    for idx, q_data in enumerate(st.session_state.quiz_question_bank):
                        with st.container(border=True):
                            st.markdown(f"**Question {idx+1}:** {q_data['question']}")
                            user_choice = st.session_state.quiz_options_chosen[idx] \
                                            if idx < len(st.session_state.quiz_options_chosen) \
                                            else None
                            correct_choice = q_data['correct_option']

                            if user_choice == correct_choice:
                                st.success(f"Your answer: {user_choice} (Correct ✅)")
                            else:
                                st.error(f"Your answer: {user_choice} (Incorrect ❌)")
                                st.info(f"Correct answer: {correct_choice}")
            # st.rerun()

def flashcards_on_chapter(subject, chapter):
    vector_store = load_vector_store(st.session_state.sha1_of_username, subject, chapter)
    
    if not st.session_state.flashcard_ongoing:
        st.radio("How many flashcards would you like to generate?", [5, 10, 20], key="flashcard_total_cards", horizontal=True)
        if st.button("Start Flashcards"):
            with st.spinner("Generating flashcards..."):
                st.session_state.flashcard_flashcards = generate_flashcards_from_faiss(vector_store, st.session_state.flashcard_total_cards)
            if st.session_state.flashcard_flashcards:
                st.session_state.flashcard_ongoing = True
                st.session_state.flashcard_current_card = 0
                st.session_state.record_added = False
                st.session_state.flashcard_show_answer = False
                st.session_state.completed = True
                st.session_state.flashcard_start_time = time.time()
                st.rerun()
            else:
                st.error("Could not generate flashcards. Please check your document or try again.")
    else:
        idx = st.session_state.flashcard_current_card
        total_cards = len(st.session_state.flashcard_flashcards)
        if idx < total_cards:
            current_card = st.session_state.flashcard_flashcards[idx]
            st.markdown(f"### Flashcard {idx+1} of {total_cards}")
            st.markdown(f"<div style='font-size:24px; font-weight:bold;'>Q: {current_card['question']}</div>", unsafe_allow_html=True)
            if not st.session_state.get("flashcard_show_answer", False):
                if st.button("Show Answer"):
                    st.session_state.flashcard_show_answer = True
                    st.rerun()
            else:
                if st.button("Hide Answer"):
                    st.session_state.flashcard_show_answer = False
                    st.rerun()
                st.markdown(f"<div style='font-size:24px; font-weight:bold;'>A: {current_card['answer']}</div>", unsafe_allow_html=True)
            _, col1, _, col2, _, col3, _ = st.columns([1,2,1,2,1,2,1])
            with col1:
                if st.button("Previous", use_container_width=True) and idx > 0:
                    st.session_state.flashcard_current_card -= 1
                    st.rerun()
            with col2:
                if st.button("End Flashcards", use_container_width=True):
                    st.session_state.flashcard_ongoing = False
                    st.rerun()
            with col3:
                if st.button("Next", use_container_width=True) and idx < total_cards - 1:
                    st.session_state.flashcard_current_card += 1
                    st.rerun()
        else:
            st.session_state.flashcard_ongoing = False
            st.success("You've gone through all the flashcards!")
            if st.button("End Flashcards", use_container_width=True):
                st.session_state.flashcard_ongoing = False
                st.rerun()

def mindmap_on_chapter(subject, chapter):
    """
    Generates and displays a mind map for the selected chapter using its vector store.
    """
    vector_store = load_vector_store(st.session_state.sha1_of_username, subject, chapter)
    st.write("Visualize the key concepts and their relationships from your study material.")

    # Use columns for button layout
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.session_state.mindmap_content is None:
            if st.button("✨ Generate", use_container_width=True):
                with st.spinner("AI is creating your mind map..."):
                    # Call the backend function to get the mind map in Mermaid format
                    mermaid_syntax = generate_mindmap_from_faiss(vector_store)
                    if mermaid_syntax:
                        st.session_state.mindmap_content = mermaid_syntax
                        st.rerun()
                    else:
                        st.error("Failed to generate mind map. Please try again or check your uploaded materials.")
    
    with col2:
        # Show "Regenerate" button if a mind map already exists
        if st.session_state.mindmap_content is not None:
            if st.button("🔄 Regenerate", use_container_width=True):
                st.session_state.mindmap_content = None # Clear existing content
                with st.spinner("AI is creating a new mind map..."):
                    mermaid_syntax = generate_mindmap_from_faiss(vector_store)
                    if mermaid_syntax:
                        st.session_state.mindmap_content = mermaid_syntax
                        st.rerun()
                    else:
                        st.error("Failed to generate mind map. Please try again.")

    # Display the generated mind map
    if st.session_state.mindmap_content:
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### Your Mind Map:")
            components.html(get_mermaid_html(st.session_state.mindmap_content), height=500, scrolling=True)
    else:
        st.info("Click '✨ Generate' to create a mind map from your chapter materials.")

def exam_on_chapter(subject, chapter):
    vector_store = load_vector_store(st.session_state.sha1_of_username, subject, chapter)

    if not st.session_state.exam_ongoing:
        st.radio("How many questions would you like in the exam?", [5, 10, 20], key="exam_total_questions", horizontal=True)
        st.number_input(
            "How many total marks would you like in the exam?",
            key="exam_total_score",
            min_value=1,
            step=1, 
            value=10
        )
        if st.button("Start Exam"):
            with st.spinner("Generating exam..."):
                st.session_state.exam_question_bank = generate_exam_from_faiss(vector_store, st.session_state.exam_total_score, st.session_state.exam_total_questions)
            if st.session_state.exam_question_bank:
                st.session_state.exam_ongoing = True
                st.session_state.exam_score = 0
                st.session_state.exam_question_number = 0
                st.session_state.exam_answers_given = []
                st.session_state.exam_correct_answers = []
                st.session_state.exam_review_mode = False
                st.session_state.exam_evaluated = False
                st.session_state.exam_answer_scores = []
                st.session_state.exam_scores_obtained = []
                st.session_state.exam_balloons = False
                st.session_state.exam_ended = False
                # st.session_state.exam_total_questions = len(st.session_state.exam_question_bank)
                st.rerun()
            else:
                st.error("Could not generate an exam. Please check your document or try again.")
    else:
        q_idx = st.session_state.exam_question_number
        total_qs = len(st.session_state.exam_question_bank)
        if  q_idx < total_qs and not st.session_state.exam_ended:
            current_question = st.session_state.exam_question_bank[q_idx]
            ques_inc, exam_end = create_exam_question(current_question['question'], q_idx)
            if ques_inc > 0:
                st.session_state.exam_question_number += ques_inc
                st.rerun()
            if exam_end:
                st.session_state.exam_ended = True
                # st.session_state.exam_question_number -= ques_inc
                st.rerun()
        else:
            if not st.session_state.exam_evaluated:
                with st.spinner("Evaluating exam..."):
                    for i in range(len(st.session_state.exam_answers_given)):
                        st.session_state.exam_scores_obtained.append(evaluate_exam(st.session_state.exam_question_bank[i]['answer'], st.session_state.exam_answers_given[i], st.session_state.exam_question_bank[i]['score']))
                    st.session_state.exam_score = sum(st.session_state.exam_scores_obtained)
                st.session_state.exam_evaluated = True
            # print(st.session_state.exam_total_score)
            st.markdown(f"## Exam Complete! Your Score: {st.session_state.exam_score} / {st.session_state.exam_total_score}")
            if st.session_state.exam_balloons == False:
                if st.session_state.exam_score > 0:
                    st.balloons()
                st.session_state.exam_balloons = True
            _,col1, _, col2,_ = st.columns([1,1,1,1,1])
            with col1:
                if st.button("End Exam", use_container_width=True):
                    st.session_state.exam_ongoing = False
                    st.rerun()
            with col2:
                if st.button("Review Answers", use_container_width=True):
                    st.session_state.exam_review_mode = True
                    st.rerun()
            
            if st.session_state.exam_review_mode:
                with st.container(height=500, border=True):
                    if st.button("Close Review"):
                        st.session_state.exam_review_mode = False
                        st.rerun()
                    st.markdown("### 🧐 Review Your Answers")
                    for idx, q_data in enumerate(st.session_state.exam_question_bank):
                        with st.container(border=True):
                            st.markdown(f" Question {idx+1}: {q_data['question']}")
                            user_answer = st.session_state.exam_answers_given[idx] if idx < len(st.session_state.exam_answers_given) else None
                            obtained_marks = st.session_state.exam_scores_obtained[idx] if idx < len(st.session_state.exam_scores_obtained) else 0.0

                            st.markdown(f"Your answer: {user_answer}")
                            st.markdown(f"Correct answer: {q_data['answer']}")
                            st.markdown(f" - Obtained marks {obtained_marks} out of {float(q_data['score'])}")


def open_a_chapter():
    if not st.session_state.app_layout == "wide":
        st.session_state.app_layout = "wide"
        st.rerun()

    if st.session_state.selected_subject is not None and st.session_state.selected_chapter is not None:
        if st.button("🏠 Home"):
            st.session_state.page = "🏠 Home"
            st.rerun()
        col1, _, col2, _, _ = st.columns([1, 1, 1, 1, 1])
        with col1:
            st.header(f"Subject: {st.session_state.selected_subject}")
        with col2:
            st.subheader(f"📖 {st.session_state.selected_chapter}")

        # if st.button("Go to homepage"):
        #     st.session_state.page = "🏠 Home"
        #     st.rerun()
        # Upload Material
        file_up_col1, file_up_col2, file_up_col3 = st.columns([1, 3, 1])
        with file_up_col1:
            with st.container(border=True):
                if st.button("Chat with AI", use_container_width=True, key="chat_ai"):
                    st.session_state.chapter_mode = "Chat with AI about this chapter"
                    st.rerun()

                if st.button("Take a quiz", key="take_quiz", use_container_width=True):
                    st.session_state.chapter_mode = "Take a quiz on this chapter"
                    st.rerun()

                if st.button("Generate flashcards", key="gen_flashcards", use_container_width=True):
                    st.session_state.chapter_mode = "Generate flashcards for this chapter"
                    st.rerun()

                if st.button("Create mindmap", key="create_mindmap", use_container_width=True):
                    st.session_state.chapter_mode = "Create mindmap for this chapter"
                    st.rerun()

                if st.button("Take exam", key="take_exam", use_container_width=True):
                    st.session_state.chapter_mode = "Take exam on this chapter"
                    st.rerun()
        with file_up_col2:
            with st.container(border=True):
                st.subheader(f"Mode: {st.session_state.chapter_mode}")
                if st.session_state.vector_store_exists:
                    if st.session_state.chapter_mode == "Chat with AI about this chapter":
                        chat_with_ai_about_chapter(st.session_state.selected_subject, st.session_state.selected_chapter)
                    elif st.session_state.chapter_mode == "Take a quiz on this chapter":
                        quiz_on_chapter(st.session_state.selected_subject, st.session_state.selected_chapter)
                    elif st.session_state.chapter_mode == "Generate flashcards for this chapter":
                        flashcards_on_chapter(st.session_state.selected_subject, st.session_state.selected_chapter)
                    elif st.session_state.chapter_mode == "Create mindmap for this chapter":
                        mindmap_on_chapter(st.session_state.selected_subject, st.session_state.selected_chapter)
                    elif st.session_state.chapter_mode == "Take exam on this chapter":
                        exam_on_chapter(st.session_state.selected_subject, st.session_state.selected_chapter)
                else:
                    st.warning("No vector store found for this chapter. Please upload materials to enable chapter functionalities.")
        with file_up_col3:
            uploaded_file = st.file_uploader("Upload study material (PDF):", type=["pdf"])
            if uploaded_file is not None:
                upload_material(st.session_state.sha1_of_username, 
                                st.session_state.selected_subject, 
                                st.session_state.selected_chapter, 
                                uploaded_file)
                st.success("File uploaded successfully!")
            if st.button("Process Uploaded Materials"):
                create_and_save_vector_store(st.session_state.sha1_of_username, 
                                             st.session_state.selected_subject, 
                                             st.session_state.selected_chapter)
                # st.success("File processed successfully!")
            materials_dir = get_material(st.session_state.sha1_of_username, 
                                         st.session_state.selected_subject, 
                                         st.session_state.selected_chapter)
            if materials_dir:
                selected_file = st.selectbox(
                    "Select a study material to delete:",
                    materials_dir,
                    key="delete_selectbox"  # unique key avoids caching issues
                )
                if st.button("Delete", key="delete_btn"):
                    file_path_to_delete = os.path.join(
                        f"{st.session_state.sha1_of_username} \
                            /materials/{st.session_state.selected_subject} \
                            /{st.session_state.selected_chapter}",
                        selected_file
                    ) if selected_file else None

                    if file_path_to_delete and os.path.exists(file_path_to_delete):
                        os.remove(file_path_to_delete)
                        st.success(f"{selected_file} deleted successfully!")

                        # reset selectbox state so it doesn’t hold deleted file
                        st.session_state.delete_selectbox = None  

                        # rebuild vector store after deletion
                        create_and_save_vector_store(
                            st.session_state.sha1_of_username,
                            st.session_state.selected_subject,
                            st.session_state.selected_chapter
                        )
                        st.rerun()
                    else:
                        st.error("Selected item does not exist.")
    else:
        if st.button("🏠 Home"):
            st.session_state.page = "🏠 Home"
            st.rerun()
        st.warning("Please select a subject and chapter from the home page.")


# ================ Temporary Chat Functionality =================
def temporary_chat():
    # st.header("📤 Temporary Chat")
    st.markdown("<h2 style='text-align: center;'>📤 Temporary Chat</h2>", unsafe_allow_html=True)

    if not st.session_state.app_layout == "wide":
        st.session_state.app_layout = "wide"
        st.rerun()

    col1, col2, _ = st.columns([1, 3, 1])
    with col1:
        st.info(" ⚠️ This is a temporary chat. All messages will be lost once you logout from current user.")
        st.markdown("---")
        fileuploader = st.file_uploader("Upload study material (PDF, DOCX, TXT):", type=["pdf", "docx", "txt"])
        if fileuploader is not None:
            alert_placeholder = st.empty()
            if st.button("Upload and Process"):
                info = ""
                with st.spinner("Uploading and processing file..."):
                    info = upload_material(st.session_state.sha1_of_username, "Temporary", "Temporary Chat", fileuploader)
                    create_and_save_vector_store(st.session_state.sha1_of_username, "Temporary", "Temporary Chat")
                    st.rerun()
                if info == "success":
                    alert_placeholder.success("File uploaded successfully!")
                elif info == "duplicate":
                    alert_placeholder.warning("File already uploaded!")
                else:
                    alert_placeholder.error("File upload failed! Error: " + info[1])
                time.sleep(1)
                alert_placeholder.empty()
                st.rerun()
    with col2:
        chat_container = st.container(width=900, height=620, border=True)
        vector_store = load_vector_store(st.session_state.sha1_of_username, "Temporary", "Temporary Chat")
        with chat_container:
            conv_container = st.container(width=900, height=520, border=False)
            with conv_container:
                for message in st.session_state.temp_chat_messages:
                    if message["role"] == "user":
                        st.chat_message("user").markdown(message["content"])
                    else:
                        st.chat_message("assistant").markdown(message["content"])

            query = st.chat_input("Ask anything...")

            with conv_container:
                if query:
                    if prompt := query:
                        st.session_state.temp_chat_messages.append({"role": "user", "content": prompt})
                        st.chat_message("user").markdown(prompt)

                        with st.spinner("AI is typing..."):
                            response = get_chat_response(prompt, vector_store)
                            st.session_state.temp_chat_messages.append({"role": "assistant", "content": response})
                            st.chat_message("assistant").markdown(response)


# ================ Chat with AI Functionality =================
def chat_with_AI():
    st.header("🧠 Chat with AI")
    
    
    if not st.session_state.app_layout == "centered":
        st.session_state.app_layout = "centered"
        st.rerun()
    
    st.session_state.chat_history = get_chat_history(st.session_state.sha1_of_username)
    conv_container = st.container(width=900, height=530, border=True)
    with conv_container:
        if st.session_state.chat_history:
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
    query = st.chat_input("Ask anything...")
    if query:
        with conv_container:
            if prompt := query:
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                add_chat_message(st.session_state.sha1_of_username, "user", prompt)

            with st.chat_message("assistant"):
                with st.spinner("AI is typing..."):
                    response = get_chat_response_general(prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    add_chat_message(st.session_state.sha1_of_username, "assistant", response)
                    st.markdown(response)



# ================ Login or Signup Functionality =================
def login_or_signup():
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    login_or_signup_error_alert = st.empty()# Create 6 columns: 1 spacer, 4 button columns, 1 spacer
    spacer_left, col1, col2, col3, spacer_right = st.columns([1, 2, 2, 2, 1])

    with col1:
        if st.button("Login", use_container_width=True):
            if st.session_state.username and st.session_state.password:
                if login_user(st.session_state.username, st.session_state.password):
                    st.session_state.logged_in = True
                    st.session_state.app_layout = "wide"
                    st.session_state.sha1_of_username = generate_sha1_hash(st.session_state.username)
                    login_or_signup_error_alert.success("Logged in successfully!")
                    st.rerun()
                else:
                    login_or_signup_error_alert.error("Incorrect username or password!")
            else:
                login_or_signup_error_alert.error("Please enter both username and password.")

    with col2:
        if st.button("Sign Up", use_container_width=True):
            if st.session_state.username and st.session_state.password:
                signup_user(st.session_state.username, st.session_state.password)
                login_or_signup_error_alert.success("Signed up successfully! Please log in.")
            else:
                login_or_signup_error_alert.error("Please enter both username and password.")

    with col3:
        if st.button("Change Password", use_container_width=True):
            st.session_state.reset_password = True
            st.rerun()

def reset_password():
    username = st.text_input("username", key="username_to_reset")
    oldPassword = st.text_input("Old Password", type="password", key="old_password_reset")
    newPassword = st.text_input("New Password", type="password", key="new_password_reset")
    alert_placeholder = st.empty()
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Reset Password", key="ResetPassword", use_container_width=True):
            try: 
                if change_password(username, oldPassword, newPassword):
                    alert_placeholder.success("Successfully reset password!")
                    st.session_state.reset_password = False
                    st.rerun()
            except Exception as e:
                st.write(e)
                alert_placeholder.error("Kindly recheck the username and passwords!")
    with col2:
        if st.button("Cancel", key="cancel_reset_password", use_container_width=True):
            st.session_state.reset_password = False
            st.rerun()

def logout(setting_default_function):
    st.session_state.shown_login_alert = False
    if st.button("🚪 Logout", use_container_width=True, key="logout"):
        # Reset all session state variables to defaults
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        setting_default_function()
        st.rerun()



# ===== Setting defaults =====
def setting_defaults():
    st.session_state.setdefault('selected_subject', None)
    st.session_state.setdefault('selected_chapter', None)
    st.session_state.setdefault('add_chap_clicked', False)
    st.session_state.setdefault('add_subj_clicked', False)
    st.session_state.setdefault('opened_chat_with_AI', False)
    st.session_state.setdefault('not_opened_chat_with_AI', False)
    

    st.session_state.setdefault('vector_store_exists', False)
    st.session_state.setdefault('record_added', False)
    # st.session_state.setdefault('total_flashcards', [])
    st.session_state.setdefault('completed', True)

    def login_signup_session_variables():
        st.session_state.setdefault('sha1_of_username', None)
        st.session_state.setdefault('username', None)
        st.session_state.setdefault('password', None)
        st.session_state.setdefault('logged_in', False)
        st.session_state.setdefault('reset_password', False)
        st.session_state.setdefault('signup_clicked', False)
        st.session_state.setdefault('login_clicked', False)
        st.session_state.setdefault('shown_login_alert', False)
    login_signup_session_variables()

    st.session_state.setdefault('chapter_mode', "Chat with AI about this chapter")
    st.session_state.setdefault('app_layout', "centered")
    if 'page' not in st.session_state:
        st.session_state.page = "🏠 Home"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # AI Chat
    st.session_state.setdefault("chat_history", [])

    # Temporary Chat
    st.session_state.setdefault("temp_chat_messages", [])

    # Quiz
    def quiz_session_variables():
        st.session_state.setdefault("quiz_ongoing", False)
        st.session_state.setdefault("quiz_score", 0)
        st.session_state.setdefault("quiz_question_number", 0)
        st.session_state.setdefault("quiz_question_bank", [])
        st.session_state.setdefault("quiz_ended", False)
        st.session_state.setdefault("quiz_total_questions", 5)
        st.session_state.setdefault("quiz_review_mode", False)
        st.session_state.setdefault("quiz_balloons", False)
        st.session_state.setdefault("quiz_options_chosen", [])
    quiz_session_variables()

    # Flashcards
    def flashcard_session_variables():
        st.session_state.setdefault("flashcard_ongoing", False)
        st.session_state.setdefault("flashcard_current_card", 0)
        st.session_state.setdefault("flashcard_total_cards", 5)
        st.session_state.setdefault("flashcard_flashcards", [])
        st.session_state.setdefault("flashcard_show_answer", False)
        st.session_state.setdefault("flashcard_start_time", None)
    flashcard_session_variables()

    # Chapter exam
    def exam_session_variables():
        st.session_state.setdefault("exam_ongoing", False)
        st.session_state.setdefault("exam_total_questions", 5)
        st.session_state.setdefault("exam_total_score", 5)
        st.session_state.setdefault("exam_ended", False)
        st.session_state.setdefault("exam_review_mode", False)
        st.session_state.setdefault("exam_balloons", False)
        st.session_state.setdefault("exam_score", 0)
        st.session_state.setdefault("exam_question_number", 0)
        st.session_state.setdefault("exam_question_bank", [])
        st.session_state.setdefault("exam_answers_given", [])
        st.session_state.setdefault("exam_scores_obtained", [])
        st.session_state.setdefault("exam_evaluated", False)
    exam_session_variables()

    # Mindmap
    def mindmap_session_variables():
        st.session_state.setdefault("mindmap_content", None)
    mindmap_session_variables()

    # general chat
    def general_chat_session_variables():
        st.session_state.setdefault("general_chat_history", [])
    general_chat_session_variables()
