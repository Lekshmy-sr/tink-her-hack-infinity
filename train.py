import pandas as pd
from sklearn.ensemble import RandomForestClassifier

df = pd.read_csv("dataset.csv")

X = df.drop("risk", axis=1)
y = df["risk"]

model = RandomForestClassifier()
model.fit(X,y)
import joblib

joblib.dump(model, "risk_model.pkl")