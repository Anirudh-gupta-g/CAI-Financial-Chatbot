# -*- coding: utf-8 -*-
"""CAI TRIAL

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1DZKn6uzxnZyJYKrX_DSN4KzQHsp_5ON6
"""

import re
import numpy as np
import PyPDF2
import faiss
import streamlit as st
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from transformers import pipeline

#########################
# Data Collection & Preprocessing
#########################
def extract_text_from_pdf(pdf_file):
    """Extract text from an Uploaded PDF file."""
    text = ""
    reader = PyPDF2.PdfReader(pdf_file)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def clean_text(text):
    """Clean the extracted text."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text, chunk_size=500, overlap=50):
    """
    Split text into overlapping chunks.
    
    Parameters:
        text (str): The text to be chunked.
        chunk_size (int): Number of words per chunk.
        overlap (int): Number of overlapping words between chunks.
        
    Returns:
        list of str: A list of text chunks.
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def process_pdfs(pdf_files, chunk_size=500, overlap=50):
    """
    Process multiple uploaded PDF files into text chunks.
    
    Parameters:
        pdf_files (list): List of UploadedFile objects.
        chunk_size (int): Number of words per chunk.
        overlap (int): Overlap in words between chunks.
        
    Returns:
        list: Combined list of all text chunks.
    """
    all_chunks = []
    for pdf_file in pdf_files:
        text = extract_text_from_pdf(pdf_file)
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)
        all_chunks.extend(chunks)
    return all_chunks

#########################
# Indexing & Embedding (Basic RAG)
#########################
def create_embedding_index(chunks, model):
    """
    Compute embeddings for text chunks and build a FAISS index.
    
    Parameters:
        chunks (list): List of text chunks.
        model (SentenceTransformer): Pre-trained embedding model.
        
    Returns:
        tuple: (FAISS index, numpy array of embeddings)
    """
    embeddings = model.encode(chunks, convert_to_tensor=False)
    embeddings = np.array(embeddings).astype("float32")
    d = embeddings.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(embeddings)
    return index, embeddings

def create_bm25_index(chunks):
    """
    Build a BM25 index from the text chunks.
    
    Parameters:
        chunks (list): List of text chunks.
        
    Returns:
        tuple: (BM25 index, tokenized corpus)
    """
    tokenized_corpus = [chunk.lower().split() for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    return bm25, tokenized_corpus

#########################
# Retrieval & Reranking (Advanced RAG)
#########################
def retrieve(query, chunks, embedding_index, embeddings, embed_model, bm25, tokenized_corpus, cross_encoder, top_k=5):
    """
    Retrieve relevant chunks for a given query.
    
    The function:
      - Validates the query (input-side guard rail)
      - Retrieves candidates using FAISS and BM25
      - Combines candidates and re-ranks them with a cross-encoder
    
    Returns:
        tuple: (top candidate chunk, confidence score, ranked candidate list)
    """
    # Input-Side Guard Rail: Basic filtering for financial-related keywords.
    def retrieve(query, chunks, embedding_index, embeddings, embed_model, bm25, tokenized_corpus, cross_encoder, top_k=5):
    # Updated guard rail keywords
        finance_keywords = [
        'revenue', 'profit', 'financial', 'income', 'expense', 'cash', 
        'growth', 'market', 'cost', 'margin', 'operating'
    ]
    # Now it will pass if the query contains any of these words
    if not any(word in query.lower() for word in finance_keywords):
        st.warning("Query does not appear to be related to financial data.")
        return None

    # --- rest of the function remains the same ---
    query_embedding = embed_model.encode([query], convert_to_tensor=False)
    ...

    # FAISS retrieval using embeddings
    query_embedding = embed_model.encode([query], convert_to_tensor=False)
    query_embedding = np.array(query_embedding).astype("float32")
    distances, indices = embedding_index.search(query_embedding, top_k)
    faiss_candidates = [chunks[i] for i in indices[0]]

    # BM25 retrieval using keyword matching
    tokenized_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_top_indices = np.argsort(bm25_scores)[::-1][:top_k]
    bm25_candidates = [chunks[i] for i in bm25_top_indices]

    # Combine unique candidates
    candidate_set = list(set(faiss_candidates + bm25_candidates))
    if not candidate_set:
        return "No relevant information found.", 0, []

    # Re-ranking with cross encoder
    cross_inputs = [(query, cand) for cand in candidate_set]
    cross_scores = cross_encoder.predict(cross_inputs)
    ranked_candidates = sorted(zip(candidate_set, cross_scores), key=lambda x: x[1], reverse=True)

    # Output-side guard rail: flag low-confidence answers.
    top_candidate, top_score = ranked_candidates[0]
    if top_score < 0.3:  # threshold for low confidence (for demonstration)
        st.info("Low confidence in retrieved answer.")

    return top_candidate, top_score, ranked_candidates

#########################
# Response Generation using a Small Open-Source Language Model
#########################
def generate_response(query, context, generator, max_new_tokens=150):
    """
    Generate a synthesized response based on the query and retrieved context.
    
    Parameters:
        query (str): The user query.
        context (str): Retrieved text context.
        generator: A text-generation pipeline.
        max_length (int): Maximum length of generated text.
        
    Returns:
        str: The generated answer.
    """
    prompt = f"Question: {query}\nContext: {context}\nAnswer:"
    generated = generator(prompt, max_new_tokens=max_new_tokens, num_return_sequences=1)
    return generated[0]['generated_text']

#########################
# UI Development with Streamlit
#########################
def main():
    st.title("Financial Statements RAG System with Response Generation")
    st.write("This system retrieves information from the last two years of financial statements and generates a synthesized answer.")

    # Ask the user to upload 2 PDF files.
    uploaded_files = st.file_uploader("Upload 2 PDF files", accept_multiple_files=True, type=["pdf"])

    if uploaded_files and len(uploaded_files) == 2:
        st.write("Processing PDF files...")
        chunks = process_pdfs(uploaded_files, chunk_size=500, overlap=50)
        st.write(f"Total text chunks generated: {len(chunks)}")

        # Load models for embedding, re-ranking, and response generation
        with st.spinner("Loading models..."):
            embed_model = SentenceTransformer('all-MiniLM-L6-v2')
            cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            # Load a small open-source language model for text generation (e.g., distilgpt2)
            generator = pipeline("text-generation", model="distilgpt2")
        
        # Build indexes
        st.write("Building vector index with FAISS...")
        embedding_index, embeddings = create_embedding_index(chunks, embed_model)
        st.write("Building BM25 index...")
        bm25, tokenized_corpus = create_bm25_index(chunks)
        st.success("Indices built successfully!")

        # Accept user query via UI
        st.header("Query Financial Data")
        query = st.text_input("Enter your financial query:")
        if st.button("Submit Query") and query:
            retrieval_result = retrieve(query, chunks, embedding_index, embeddings, embed_model, bm25, tokenized_corpus, cross_encoder, top_k=5)
            if retrieval_result:
                top_candidate, confidence, ranked_candidates = retrieval_result
                st.write("### Retrieved Context:")
                st.write(top_candidate)
                st.write(f"**Confidence Score:** {confidence:.2f}")
                # Generate a final answer using the retrieved context and the generator
                final_answer = generate_response(query, top_candidate, generator, max_new_tokens=150)
                st.write("### Generated Answer:")
                st.write(final_answer)
            else:
                st.write("No answer due to guard rail filtering.")
    else:
        st.info("Please upload exactly 2 PDF files to proceed.")

if __name__ == "__main__":
    main()
