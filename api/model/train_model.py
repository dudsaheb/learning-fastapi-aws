import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import joblib

# =========================
# 1️⃣ Sample Dataset (Simple)
# =========================
# You can replace this with a real dataset later
data = pd.DataFrame({
    "area": [800, 1000, 1200, 1500, 1800, 2000, 2500, 3000],
    "bedrooms": [1, 2, 2, 3, 3, 4, 4, 5],
    "bathrooms": [1, 1, 2, 2, 2, 3, 3, 4],
    "price": [45, 60, 75, 90, 110, 130, 160, 200]  # prices in lakhs
})

# =========================
# 2️⃣ Split Dataset
# =========================
X = data[["area", "bedrooms", "bathrooms"]]
y = data["price"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# =========================
# 3️⃣ Train Model
# =========================
model = LinearRegression()
model.fit(X_train, y_train)

# =========================
# 4️⃣ Save Model
# =========================
joblib.dump(model, "model.pkl")
print("✅ model.pkl created successfully!")

# =========================
# 5️⃣ Test Model (Optional)
# =========================
sample = [[1800, 3, 2]]
predicted_price = model.predict(sample)[0]
print(f"Predicted price for {sample}: {round(predicted_price, 2)} Lakhs")
