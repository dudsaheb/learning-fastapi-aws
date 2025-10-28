import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import joblib
import os
import json
from datetime import datetime

# ====================================================
# 📘 1️⃣ Sample Dataset
# ====================================================
# Note: Prices are in Lakhs (1 Lakh = ₹100,000)
data = pd.DataFrame({
    "area": [800, 1000, 1200, 1500, 1800, 2000, 2500, 3000],
    "bedrooms": [1, 2, 2, 3, 3, 4, 4, 5],
    "bathrooms": [1, 1, 2, 2, 2, 3, 3, 4],
    "price": [45, 60, 75, 90, 110, 130, 160, 200]  # in Lakhs
})

# ====================================================
# ✂️ 2️⃣ Split Dataset into Train/Test
# ====================================================
X = data[["area", "bedrooms", "bathrooms"]]
y = data["price"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ====================================================
# 🤖 3️⃣ Train Model
# ====================================================
model = LinearRegression()
model.fit(X_train, y_train)

# ====================================================
# 💾 4️⃣ Save Model to /api/model/model.pkl
# ====================================================
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")

joblib.dump(model, MODEL_PATH)
print(f"✅ Model trained and saved at: {MODEL_PATH}")

# ====================================================
# 🧠 5️⃣ Generate Model Metadata (for /predict/info)
# ====================================================
model_info = {
    "model_name": "Linear Regression - House Price Predictor",
    "framework": "scikit-learn",
    "version": "1.0",
    "trained_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "target_variable": "price (in Lakhs)",
    "features": list(X.columns),
    "sample_count": len(data),
    "author": "Shaik Dud Saheb",
}

MODEL_INFO_PATH = os.path.join(MODEL_DIR, "model_info.json")
with open(MODEL_INFO_PATH, "w") as f:
    json.dump(model_info, f, indent=4)

print(f"🧾 Model metadata saved at: {MODEL_INFO_PATH}")

# ====================================================
# 🧪 6️⃣ Test Model Output
# ====================================================
sample = [[1800, 3, 2]]
predicted_price_lakh = model.predict(sample)[0]
predicted_price_inr = predicted_price_lakh * 100000  # Convert to Rupees

print(f"💡 Test sample: {sample}")
print(f"🏠 Predicted price: {round(predicted_price_lakh, 2)} Lakhs ≈ ₹{round(predicted_price_inr, 2):,.2f}")
