These two scripts demonstrate fine tuning the BERT transformer model to learn relationships between medical terminology labeled from patients' medical history report.  

Script #1 (non-contextual):
The model takes in two inputs--- an entity (e.g., smokes) and an attribute (e.g., frequently) and learns whether they are RELATED or NOT_RELATED (i.e., attribute modifies the entity).

Model results:
Validation Accuracy:  88.93%
Precision:            80.62%
Recall:               74.39%
F1 Score:             77.38%

Script #2: contextual
This model takes a single input that is the entire medical document containing added context with the entity and attribute labeled with tags, and learns the labels RELATED or NOT_RELATED. 
Taking advantage of BERT's language contextual abilities resulted in significant model performance improvement.

Validation Accuracy:  94.45%
Precision:            97.35%
Recall:               81.18%
F1 Score:             88.53%
