from transformers import BertTokenizerFast, BertForSequenceClassification
import csv
import pandas as pd
import numpy as np
model_path = "./moralization-bert-base-uncased"
tokenizer = BertTokenizerFast.from_pretrained(model_path)
model = BertForSequenceClassification.from_pretrained(model_path)
max_length = 512

def get_prediction(text):
    # prepare our text into tokenized sequence
    inputs = tokenizer(text, padding=True, truncation=True, max_length= max_length, return_tensors="pt")
    # perform inference to our model
    outputs = model(**inputs)
    # get output probabilities by doing softmax
    probs = outputs[0].softmax(1)
    # executing argmax function to get the candidate label
    return [0,1][probs.argmax()] # 0 is Non-Moral, 1 is Moral

def prediction_csv(filepath):
    #CHANGE WITH REAL HEADERS
    header = ['a', 'b', 'c', 'd', 'text', 'e', 'f', 'g']
    df = pd.read_csv(filepath, names=header)
    rows = len(df.index)
    prediction_vals = []
    for i in range(0,rows):
        prediction = get_prediction(df['text'][i])
        prediction_vals.append(prediction)
    df['Moralization'] = prediction_vals
    df.to_csv
    return df

if __name__ == '__main__':
    prediction_csv('filepath')