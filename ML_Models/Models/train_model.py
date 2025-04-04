
import numpy as np
import pandas as pd
import joblib
import mlflow
import tensorflow as tf
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, roc_auc_score, mean_squared_error, r2_score
from mlflow.models.signature import infer_signature
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


# Initialize MLflow Experiment
mlflow.set_experiment("Customer Churn")

df = pd.read_csv('/home/prakda/Homework_MLFlow/ML_Models/Dataset/Customer-Churn.csv')

df = df.drop(columns=['customerID'], errors='ignore')

# Handle missing values and convert data types
df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')

# Check for missing values and fill with 0
df[['tenure', 'MonthlyCharges', 'TotalCharges']] = df[['tenure', 'MonthlyCharges', 'TotalCharges']].fillna(0)

# Convert SeniorCitizen to object type for encoding
df['SeniorCitizen'] = df['SeniorCitizen'].astype('object')

# Standardization for numeric columns
scaler = StandardScaler()
df[['tenure', 'MonthlyCharges', 'TotalCharges']] = scaler.fit_transform(df[['tenure', 'MonthlyCharges', 'TotalCharges']])

# Label Encoding for binary columns
label_enc_cols = ['gender', 'SeniorCitizen', 'Partner', 'Dependents', 'PhoneService', 'PaperlessBilling', 'Churn']
le = LabelEncoder()
for col in label_enc_cols:
    df[col] = le.fit_transform(df[col])

# One-Hot Encoding for nominal columns
ohe_cols = ['MultipleLines', 'InternetService', 'OnlineSecurity', 'OnlineBackup', 
            'DeviceProtection', 'TechSupport', 'StreamingTV', 'StreamingMovies', 
            'Contract', 'PaymentMethod']

df = pd.get_dummies(df, columns=ohe_cols, drop_first=True)

# Replace inf/-inf with NaN and fill with 0
df = df.replace([np.inf, -np.inf], np.nan)
df = df.fillna(0).astype(int)


# Feature Engineering


# Feature and Target Separation
X = df.drop(columns=['Churn'])
y = df['Churn']

# Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Convert input_example to DataFrame for MLflow
input_example = X_train.head(1)


# Evaluation Function


def get_model_metrics(X_test, y_test, y_pred, model, model_name):
    # Confusion Matrix
    conf_matrix = confusion_matrix(y_test, y_pred)
    TN, FP, FN, TP = conf_matrix.ravel()

    # Classification Report
    report = classification_report(y_test, y_pred, output_dict=True)

    # ROC-AUC Score
    roc_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]) if hasattr(model, "predict_proba") else roc_auc_score(y_test, model.predict(X_test))

    # Accuracy
    accuracy = accuracy_score(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    # Compile all metrics
    metrics = {
        "model": model_name,
        "confusion_matrix_tn": TN,
        "confusion_matrix_fp": FP,
        "confusion_matrix_fn": FN,
        "confusion_matrix_tp": TP,
        "class_0_precision": report['0']['precision'],
        "class_0_recall": report['0']['recall'],
        "class_0_f1_score": report['0']['f1-score'],
        "class_1_precision": report['1']['precision'],
        "class_1_recall": report['1']['recall'],
        "class_1_f1_score": report['1']['f1-score'],
        "accuracy_f1_score": report['accuracy'],
        "roc_auc_score": roc_auc,
        "accuracy": accuracy,
        "mse": mse,
        "r2_score": r2
    }

    if hasattr(model, "n_estimators"):  # For RandomForest, XGBoost, etc.
        metrics["n_estimators"] = model.n_estimators
    if hasattr(model, "max_depth"):  # For DecisionTree, RandomForest, XGBoost, etc.
        metrics["max_depth"] = model.max_depth
    # Log Learning Rate and n_estimators if available
    if hasattr(model, 'learning_rate'):
        metrics["learning_rate"] = model.learning_rate

    return metrics

# Model Training & MLflow Logging


# Dictionary of all models with hyperparameters
models = {
    "LogisticRegression": LogisticRegression(class_weight='balanced', random_state=42),
    "KNN": KNeighborsClassifier(),
    "SVM": SVC(class_weight='balanced', probability=True, random_state=42)
}

# Training and Logging Loop
for model_name, model in models.items():
    with mlflow.start_run(run_name=model_name):
        # Train Model
        model.fit(X_train, y_train)

        # Predictions
        y_pred = model.predict(X_test)

        # Evaluate
        eval_metrics = get_model_metrics(X_test, y_test, y_pred, model, model_name)

        # Log Model Type
        mlflow.log_param("model_type", model_name)

        # Log Metrics (Excluding model name)
        mlflow.log_metrics({k: v for k, v in eval_metrics.items() if k != "model"})

        # Log Model with Signature
        signature = infer_signature(X_train, model.predict(X_train))
        mlflow.sklearn.log_model(model, model_name, signature=signature, input_example=input_example)

        # Save Locally
        joblib.dump(model, f'/home/prakda/Homework_MLFlow/ML_Models/Models/trained/{model_name}.pkl')

        print(f"{model_name} training and logging completed.")


# ANN Model Training


def train_ann(epochs, model_name):
    with mlflow.start_run(run_name=model_name):
        # Define ANN
        model_ann = tf.keras.Sequential([
            tf.keras.layers.InputLayer(input_shape=(X_train.shape[1],)),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(2, activation='sigmoid')
        ])

        # Compile ANN
        model_ann.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

        # Train ANN
        history = model_ann.fit(X_train, y_train, epochs=epochs, batch_size=32, validation_data=(X_test, y_test), verbose=0)

        # Predictions
        y_pred = (model_ann.predict(X_test) > 0.5).astype(int)

        # Evaluate
        eval_metrics = get_model_metrics(X_test, y_test, y_pred, model_ann, model_name)

        # Log Model Type
        mlflow.log_param("model_type", model_name)
        
        # Log Params and Metrics
        mlflow.log_param("epochs", epochs)
        mlflow.log_metrics({k: v for k, v in eval_metrics.items() if k != "model"})

        # Log ANN Model
        mlflow.tensorflow.log_model(model_ann, model_name)

        # Save Locally
        model_ann.save(f'model/training/{model_name}.keras')

        print(f"{model_name} training and logging completed.")

# Train ANN models
train_ann(10, "ANN_10_Epochs")
train_ann(25, "ANN_25_Epochs")


# MLflow UI Instructions

print("\n All models trained and logged to MLflow.")
print("Run the following command to launch MLflow UI:")
print("mlflow ui")
print("Navigate to http://127.0.0.1:5000 to view results")
