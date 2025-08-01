# -*- coding: utf-8 -*-
"""Untitled4.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1pODEemKRKjaW0mWKx2p7Ct9MjP79qr12
"""

import os
import random
from transformers import BertTokenizer, BertForSequenceClassification
import torch
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
from torch.optim import AdamW
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


#object for extracting data from annotation files, parsing it, and returning the training data

class DataExtractor():
  def __init__ (self, folder):
    self.folder = folder
    self.entities =  ["Tobacco", "Alcohol", "Drug"]
    self.attributes = ["Status", "Type", "Method", "Amount", "Frequency", "History", "ExposureHistory", "QuitHistory"]

  # Finds and reads in all the .ann files and analogous .txt files
  def get_all_files(self):
    all_file_paths = [(os.path.join(self.folder, file), os.path.join(self.folder, file[:-4] + '.txt')) for file in os.listdir(self.folder) if file.endswith(".ann")]
    all_files = []
    for filename in all_file_paths:
      with open (filename[0]) as f:
        ann_file = f.read()
      with open (filename[1]) as f:
        txt_file = f.read()
      all_files.append((ann_file, txt_file))
    return all_files

  def insert_entity_attribute_tags(self, text, ent_start, ent_end, att_start, att_end):
    spans = sorted([
        (ent_start, ent_end, '<e>', '</e>'),
        (att_start, att_end, '<a>', '</a>')
    ], key=lambda x: x[0], reverse=True)

    for start, end, open_tag, close_tag in spans:
        text = text[:end] + close_tag + text[end:]
        text = text[:start] + open_tag + text[start:]

    return text

  def get_training_data(self):
    all_files = self.get_all_files()
    ann_files = [file[0] for file in all_files]
    text_files = [file[1] for file in all_files]  #not used in inital version, but if needed later for pulling in more sentence context
    ann_data = []
    transformed_data = []
    for ann_file, txt_file in zip(ann_files, text_files):
      pair_relations = self.extract_ann_data(ann_file, txt_file)
      ann_data.extend(pair_relations)
    for item in ann_data:
      relation = item[1]
      text = item[2]
      e_start = int(item[3][0])
      e_end = int(item[3][1])
      a_start = int(item[4][0])
      a_end = int(item[4][1])
      tagged_text = self.insert_entity_attribute_tags(text, e_start, e_end, a_start, a_end)
      transformed_data.append((tagged_text, relation))
    return transformed_data

  # function that performs the core parsing of the .ann files, finding the relevant T and E data, and labeling the T combos as related/not related
  def extract_ann_data(self, ann_file, txt_file):
    entities_temp = []
    atts_temp = []
    events = []
    id_text_dict = {}
    for line in ann_file.split('\n'): #collect relevant T and E lines
      if len(line.split('\t')) >= 2:  #some lines are empty lists
        id, label = self.get_id_and_label(line)
        if id.startswith("T"):
          text = line.split('\t')[2]  #the actual text portion
          id_text_dict[id] = text  #assign to dictionary for later lookup
          if label in self.entities:  #collect entity references (tobacco, drugs, alcohol)
            entities_temp.append(line)
          elif label in self.attributes:  #collect attributes of those entities
            atts_temp.append(line)
        if id.startswith("E"):  #collect relevant events
          if label in self.entities:  #only get the ones related to tobacco / drugs / alcohol
            events_temp = self.get_events_temp(line)  #gets just the text codes
            events.append(events_temp)
    pairs = self.get_pairs(entities_temp, atts_temp)  #get all the pairwise combinations of entities and attributes
    event_text = []
    for event in events:
      temp_event_text = []
      for ev in event:
        temp_event_text.append(id_text_dict[ev])  #look up text that corresponds to the ent/att id
      event_text.append(temp_event_text)
    pair_relations = []
    for pair_data in pairs:
      pair = pair_data[0]
      ent_loc = pair_data[1]
      att_loc = pair_data[2]
      relation = "NOT_RELATED"
      for ev_text in event_text:
        if set(pair).issubset(ev_text):  #checks to see the relation is attested somewhere in the E lines
          relation = "RELATED"
      pair_relations.append((pair, relation, txt_file, ent_loc, att_loc))
    return pair_relations

  # returns all the combinations between entity and attribute words
  def get_pairs(self, entities_temp, atts_temp):
    pairs = set(((ent.split('\t')[2], att.split('\t')[2]), (ent.split('\t')[1].split()[1],ent.split('\t')[1].split()[2]), (att.split('\t')[1].split()[1],att.split('\t')[1].split()[2])) for ent in entities_temp for att in atts_temp)
    return pairs

  #return the ids for each relation in an event line, e.g. E1	Alcohol:T2 State:T1
  def get_events_temp(self, line):
    events_temp = []
    for event in line.split()[1:]:  #line with E id removed
      text_id = event.split(':')[1]  #split off ent/att id, i.e., Alcohol:T2 -> T2
      events_temp.append(text_id)
    return events_temp  #returns list of ent/att ids, e.g., [T2, T1]

  # finds and returns the id (e.g. T1) and the label, e.g., Tobacco, Status, etc.
  def get_id_and_label(self, line):
    id = line.split()[0]
    label = line.split()[1]
    label = label.split(":")[0]
    return id, label

  #shuffles data and returns an 80-20 training - validation split
  def split_data(self, all_data):
    random.shuffle(all_data)
    training_percent = 0.8
    split_point = int(len(all_data) * training_percent)
    train_data = all_data[:split_point]
    val_data = all_data[split_point:]
    return train_data, val_data

#creating a custom dataset object, preparing it for loading into a PyTorch DataLoader for batching & training
class TextPairDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}  #retrieves the idx-th (e.g., 17th) item in each of the 3 encodings tensors
        item["labels"] = self.labels[idx]  #then adds the idx-th item for the label tensor
        return item

    def __len__(self):  #number of examples in data
        return len(self.labels)

# encodes the data, which involves joining the two text chunks (w/ separator), adding padding to length of 32, etc.  Used for training and validation data encoding
def encode_data_and_labels(tokenizer, model_data):
  label_to_id = {"NOT_RELATED": 0, "RELATED": 1}
  #ent_data = [item[0][0] for item in model_data]
  #att_data = [item[0][1] for item in model_data]
  data = [item[0] for item in model_data]
  label_texts = [item[1] for item in model_data]
  label_data = [label_to_id[label] for label in label_texts]
  # Tokenize all pairs at once; encoded includes three tensors, id, attention mask, & token type
  encoded = tokenizer(
      data,
      padding=True,
      truncation=True,
      max_length=100,
      return_tensors='pt'
  )
  labels_tensor = torch.tensor(label_data)  #this coverts our list to a tensor object
  return encoded, labels_tensor

# Trains the model
def train(model, loader, optimizer, num_epochs=3):
  model.train()
  for epoch in range(num_epochs):
    for batch in loader:  # each batch is 16 examples
      outputs = model(**batch) # here we do the actual vectorization of word chunks
      loss = outputs.loss
      loss.backward()           # computes gradients
      optimizer.step()          # update weights
      optimizer.zero_grad()     # reset gradients

def evaluate(model, val_loader):
  all_preds = []  # collects the model's predicted labels
  all_labels = []  # collects the actual labels (for eval comparison)
  model.eval()  # switches model to evaluation mode
  with torch.no_grad():  # turns off gradient tracking to speed up evaluation
      for batch in val_loader:
          outputs = model(**batch)  # make predictions
          preds = torch.argmax(outputs.logits, dim=1)  # returns 0 or 1 depending on which got a higher logit
          all_preds.extend(preds.cpu().tolist())  # adds predicted values to list
          all_labels.extend(batch["labels"].cpu().tolist())  # adds ground truth values to list
  return all_preds, all_labels

# calculates and prints precision, recall, F1, and accuracy based on predicted and true labels
def output_metrics(all_preds, all_labels):
  accuracy = accuracy_score(all_labels, all_preds)
  precision = precision_score(all_labels, all_preds, pos_label=1)  # pos_label=1 ensures we evaluate how well the model identifies the "RELATED" class
  recall = recall_score(all_labels, all_preds, pos_label=1)
  f1 = f1_score(all_labels, all_preds, pos_label=1)

  # print out metrics
  print(f"Validation Accuracy:  {accuracy:.2%}")
  print(f"Precision:            {precision:.2%}")
  print(f"Recall:               {recall:.2%}")
  print(f"F1 Score:             {f1:.2%}")


#extracting data
folder = '/content'
extractor = DataExtractor(folder)
all_data = extractor.get_training_data()
print (all_data)
#max_len = (sum([len(x[0].split()) for x in all_data])) / len(all_data)
#print (max_len)
train_data, val_data = extractor.split_data(all_data)


# model training
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased") #create the tokenizer here
model = BertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=2)

encoded, labels_tensor = encode_data_and_labels(tokenizer, train_data)
encoded_val, labels_tensor_val = encode_data_and_labels(tokenizer, val_data)

dataset = TextPairDataset(encoded, labels_tensor)  # encoded is the dict of three tensors created before, then we have our labels tensor

loader = DataLoader(dataset, batch_size=16, shuffle=True)  # batch size for training, and shuffle for each epoch when training

optimizer = AdamW(model.parameters(), lr=5e-5)
train(model, loader, optimizer)

#evaluation portion
val_dataset = TextPairDataset(encoded_val, labels_tensor_val) #convert encoded evaluation data to dataset
val_loader = DataLoader(val_dataset, batch_size=16)
all_preds, all_labels = evaluate(model, val_loader)
output_metrics(all_preds, all_labels)