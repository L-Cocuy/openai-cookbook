"""Main python module for the web crawl q and a app."""

import os
from dotenv import load_dotenv

import pandas as pd
import openai
import numpy as np
from openai.embeddings_utils import distances_from_embeddings
import tiktoken

from scrapper_utils import get_same_domain_links, crawl_and_scrape

# Load the environment variables
load_dotenv()
#Get the API key from the environment variable
openai.api_key = os.environ["OPENAI_API_KEY"]

# Define root domain to crawl
FULL_URL = "https://paradiser.at/"

urls, domain = get_same_domain_links(FULL_URL)
crawl_and_scrape(urls)


def remove_newlines(serie):
    serie = serie.str.replace('\n', ' ')
    serie = serie.str.replace('\\n', ' ')
    serie = serie.str.replace('  ', ' ')
    serie = serie.str.replace('  ', ' ')
    return serie


# Step to create a dataframe from the text files
# Create a list to store the text files
texts=[]

# Get all the text files in the text directory
for file in os.listdir("text/"):

    # Open the file and read the text
    with open("text/" + "/" + file, "r", encoding="utf-8") as f:
        text = f.read()

        # Omit the first 11 lines and the last 4 lines, then replace -, _, and #update with spaces.
        texts.append((file.replace('-',' ').replace('_', ' ').replace('#update',''), text))

# Create a dataframe from the list of texts
df = pd.DataFrame(texts, columns = ['fname', 'text'])

# Set the text column to be the raw text with the newlines removed
df['text'] = df.fname + ". " + remove_newlines(df.text)

# Create the processed directory if it doesn't exist and ensure it is empty
if not os.path.exists('processed/'):
    os.mkdir('processed/')
for file in os.listdir("processed/"):
    os.remove("processed/"+file)

df.to_csv('processed/scraped.csv')

# Step to tokenize the text
# Load the cl100k_base tokenizer which is designed to work with the ada-002 model
tokenizer = tiktoken.get_encoding("cl100k_base")

df = pd.read_csv('processed/scraped.csv', index_col=0)
df.columns = ['title', 'text']

# Tokenize the text and save the number of tokens to a new column
df['n_tokens'] = df.text.apply(lambda x: len(tokenizer.encode(x)))

# Step to split the text into chunks
max_tokens = 500

# Function to split the text into chunks of a maximum number of tokens
def split_into_many(text, max_tokens = max_tokens):

    # Split the text into sentences
    sentences = text.split('. ')

    # Get the number of tokens for each sentence
    n_tokens = [len(tokenizer.encode(" " + sentence)) for sentence in sentences]
    
    chunks = []
    tokens_so_far = 0
    chunk = []

    # Loop through the sentences and tokens joined together in a tuple
    for sentence, token in zip(sentences, n_tokens):

        # If the number of tokens so far plus the number of tokens in the current sentence is greater 
        # than the max number of tokens, then add the chunk to the list of chunks and reset
        # the chunk and tokens so far
        if tokens_so_far + token > max_tokens:
            chunks.append(". ".join(chunk) + ".")
            chunk = []
            tokens_so_far = 0

        # If the number of tokens in the current sentence is greater than the max number of 
        # tokens, go to the next sentence
        if token > max_tokens:
            continue

        # Otherwise, add the sentence to the chunk and add the number of tokens to the total
        chunk.append(sentence)
        tokens_so_far += token + 1
        
    # Add the last chunk to the list of chunks
    if chunk:
        chunks.append(". ".join(chunk) + ".")

    return chunks
    

shortened = []

# Loop through the dataframe and append the shortened text to the list of shortened texts
for row in df.iterrows():

    # If the text is None, go to the next row
    if row[1]['text'] is None:
        continue

    # If the number of tokens is greater than the max number of tokens, split the text into chunks
    if row[1]['n_tokens'] > max_tokens:
        shortened += split_into_many(row[1]['text'])
    
    # Otherwise, add the text to the list of shortened texts
    else:
        shortened.append( row[1]['text'] )

df = pd.DataFrame(shortened, columns = ['text'])
df['n_tokens'] = df.text.apply(lambda x: len(tokenizer.encode(x)))

# Create embeddings for each chunk of text
df['embeddings'] = df.text.apply(lambda x: openai.Embedding.create(input=x, engine='text-embedding-ada-002')['data'][0]['embedding'])
df.to_csv('processed/embeddings.csv')

# Add the embeddings to the dataframe
df=pd.read_csv('processed/embeddings.csv', index_col=0)
df['embeddings'] = df['embeddings'].apply(eval).apply(np.array)

# Create context for question
def create_context(question, df, max_len=1800, size="ada"):
    """
    Create a context for a question by finding the most similar context from the dataframe
    """

    # Get the embeddings for the question
    q_embeddings = openai.Embedding.create(input=question, engine='text-embedding-ada-002')['data'][0]['embedding']

    # Get the distances from the embeddings
    df['distances'] = distances_from_embeddings(q_embeddings, df['embeddings'].values, distance_metric='cosine')


    returns = []
    cur_len = 0

    # Sort by distance and add the text to the context until the context is too long
    for i, row in df.sort_values('distances', ascending=True).iterrows():
        
        # Add the length of the text to the current length
        cur_len += row['n_tokens'] + 4
        
        # If the context is too long, break
        if cur_len > max_len:
            break
        
        # Else add it to the text that is being returned
        returns.append(row["text"])

    # Return the context
    return "\n\n###\n\n".join(returns)

def answer_question(
    df,
    model="gpt-4",
    question="Am I allowed to publish model outputs to Twitter, without a human review?",
    max_len=1800,
    size="ada",
    debug=False,
    max_tokens=150,
    stop_sequence=None
):
    """
    Answer a question based on the most similar context from the dataframe texts
    """
    context = create_context(
        question,
        df,
        max_len=max_len,
        size=size,
    )
    # If debug, print the raw model response
    if debug:
        print("Context:\n" + context)
        print("\n\n")

    try:
        # Create a completions using the questin and context
        response = openai.ChatCompletion.create(
            #prompt=f"Answer the question based on the context below, and if the question can't be answered based on the context, say \"I don't know\"\n\nContext: {context}\n\n---\n\nQuestion: What is ParadiseR?\nAnswer:ParadiseR is a cooking service that provides customers with meal kits containing all the necessary ingredients to prepare gourmet meals at home. The ingredients are washed, cut, and packaged, and the meal kits are delivered to the customer's doorstep in a CO2-neutral manner. The meal kits come with simple cooking instructions, and there are various dishes to choose from, including classic, exotic, vegetarian, and meat dishes. ParadiseR also offers a subscription service where customers can receive weekly deliveries and pause or cancel the subscription at any time.\n\nQuestion: {question}\nAnswer:",
            messages=[{"role": "system", "content": f"Answer the question based on the context below, and if the question can't be answered based on the context, say \"I don't know\"\n\n"},
                      {"role": "system", "content": f"Context: {context}"},
                      {"role": "assistant", "content": "Hi, how are you doing today? What can I help you with?"},
                      {"role": "user", "content": f"Question: {question}"}
            ],
            temperature=0,
            max_tokens=max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=stop_sequence,
            model=model,
        )
        return response#["choices"][0]["text"].strip()
    except Exception as e:
        print(e)
        return ""
    

print(answer_question(df, question="What is the integral of x^2?"))

print(answer_question(df, question="Was sind die ParadiseR Abos?"))

print(answer_question(df, question="What is ParadiseR?"))

print(answer_question(df, question="What meals does ParadiseR sell?"))