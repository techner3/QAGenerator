import re
import os
import sys
import csv
from src.prompt import *
from src.logger import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from langchain_cohere import CohereRerank
from langchain.prompts import PromptTemplate
from src.exception import QAGeneratorException
from langchain.docstore.document import Document
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import TokenTextSplitter
from langchain_community.retrievers import BM25Retriever
from langchain.chains.summarize import load_summarize_chain
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

load_dotenv()

def preprocessing(file_path):

    try:
        logging.info("Preprocessing of Data Started")

        loader = PyPDFLoader(file_path)
        data = loader.load()
        logging.info("Data Loaded Sucessfully")

        question_gen = ""
        for page in data:
            question_gen += page.page_content    

        splitter_ques_gen = TokenTextSplitter(model_name= "gpt-3.5-turbo",chunk_size= 10000,chunk_overlap = 200)
        chunk_ques_gen = splitter_ques_gen.split_text(question_gen)
        document_ques_gen = [Document(page_content = t) for t in chunk_ques_gen]
        logging.info("Question Generation Chunk created Successfully")

        splitter_ans_gen = TokenTextSplitter(model_name = 'gpt-3.5-turbo',chunk_size = 1000,chunk_overlap = 100)
        document_answer_gen = splitter_ans_gen.split_documents(document_ques_gen)
        logging.info("Answer Generation Chunk created Successfully")

        return document_ques_gen,document_answer_gen
    
    except Exception as e:
        raise QAGeneratorException(e,sys)

def qa_generator(file_path):

    output_file="output/QA.csv"
    try:
        document_ques_gen, document_answer_gen = preprocessing(file_path)
        logging.info("Preprocessing done Successfully")

        llm=ChatGroq(temperature=0,model="llama3-70b-8192",api_key=os.getenv("GROQ_API_KEY"))
        logging.info("LLM Model Loaded Successfully")

        PROMPT_QUESTIONS = PromptTemplate(template=prompt_template, input_variables=['text'])
        REFINE_PROMPT_QUESTIONS = PromptTemplate(input_variables=["existing_answer", "text"],template=refine_template)
        ques_gen_chain = load_summarize_chain(llm = llm, chain_type = "refine", question_prompt=PROMPT_QUESTIONS, refine_prompt=REFINE_PROMPT_QUESTIONS)
        ques = ques_gen_chain.invoke(document_ques_gen)['output_text']
        sentence_list=ques.replace("\n\n","\n").split("\n")
        ques_list=[]
        for sentence in sentence_list:
            if bool(re.search(r'\d', sentence)):
                ques_list.append(sentence)
        logging.info("Question created successfully")

        embeddings = OllamaEmbeddings(model='mxbai-embed-large')
        vector_store = FAISS.from_documents(document_answer_gen, embeddings)
        logging.info("Data stored in vector store successfully")
        retriever = BM25Retriever.from_documents(document_answer_gen)
        ensemble_retriever = EnsembleRetriever(retrievers=[retriever, vector_store.as_retriever()], weights=[0.5, 0.5])
        compressor = CohereRerank(cohere_api_key=os.getenv("COHERE_API_KEY"))
        compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)
        logging.info("Hybrid RAG object created successfully")
        
        answer_generation_chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=compression_retriever)
        logging.info("Retrival Chain Created")

        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Question", "Answer"]) 

            for question in ques_list:
                answer = answer_generation_chain.invoke(question)["result"]
                csv_writer.writerow([question, answer])

        logging.info("Question and Answer created successfully")
        return output_file

    except Exception as e:
        raise QAGeneratorException(e,sys)