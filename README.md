# 🖼️ Visual Product Matcher

An AI-powered application to **find visually similar products** by uploading an image or providing a product image URL.  
Frontend runs on **React (Vite)**, while the backend is powered by **FastAPI + CLIP embeddings** (hidden in demo).  

---

## 🚀 Live Demo
👉 Try the app here: [https://visual-product-matcher-opal.vercel.app](https://visual-product-matcher-opal.vercel.app)

---

## ✨ Features
- 📤 Upload an image or paste an image URL  
- 🔍 Find **visually similar products** instantly  
- ⚡ Powered by **OpenAI CLIP embeddings**  
- 🎨 Clean and simple UI  
- 🌍 Fully deployed with free hosting (**Vercel + Hugging Face Spaces**)  

---

## 🛠️ Tech Stack
### 🔹 Frontend
- React (Vite)  
- Axios / Fetch for API calls  
- TailwindCSS (if applied) for styling  
- Deployed on **Vercel**

### 🔹 Backend (internal only)
- FastAPI  
- PyTorch + Transformers (CLIP Model)  
- NumPy / Pandas for data handling  
- Hosted privately on **Hugging Face Spaces** (not exposed to public)  

---

## ⚡ How It Works
1. **demo** ([Vercel link](https://visual-product-matcher-opal.vercel.app))  
2. Uploads an image (or pastes an image URL)  
3. Frontend sends the request to the backend   
4. Backend processes image → generates embeddings → finds matches  
5. Results are returned and displayed instantly  

---

## 👨‍💻 Author
**Veer Pratap Yadav**  
- 💼 [LinkedIn](https://www.linkedin.com/in/veer-pratap-yadav-a697a025b/)  
- 🐙 [GitHub](https://github.com/Veerpra123)  
- ✉️ yadavveerpratap79@gmail.com  

---

## 🚀 Demo
👉 **(Public):** [visual-product-matcher-opal.vercel.app](https://visual-product-matcher-opal.vercel.app)  
 
## 🔍 Try Searching These Products

To explore the **Visual Product Matcher**, you can upload an image or search using a URL.  
Here are some sample product categories you can try:

- 💻 **Laptop**, **Smartphone**, **Tablet**, **Smartwatch**  
- 👕 **T-shirt**, **Jeans**, **Jacket**, **Sneakers**, **Formal Shoes**  
- ⌚ **Wristwatch**, **Wireless Earbuds**, **Headphones**, **Bluetooth Speaker**  
- 🛋️ **Sofa**, **Wardrobe**, **Dining Table**, **Study Desk**, **Bookshelf**  
- 🍳 **Mixer Grinder**, **Induction Cooktop**, **Pressure Cooker**, **Microwave Oven**, **Refrigerator**  
- 🧴 **Shampoo**, **Sunscreen**, **Face Wash**, **Moisturizer**, **Perfume**  
- 🏋️ **Dumbbells**, **Treadmill**, **Yoga Mat**, **Bicycle**, **Cricket Bat**  
- 👜 **Handbag**, **Backpack**, **Leather Belt**, **Wallet**  
- 🖨️ **Printer**, **Digital Camera**, **Gaming Console**, **Power Bank**  

👉 Just **upload an image** (e.g., of a **watch or laptop**) or **paste an image URL**, and the system will return **visually similar products** from the dataset.
