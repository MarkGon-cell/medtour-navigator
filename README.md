Frontend 
# Navigate
cd medtour-navigator

# Install dependencies
npm install

# Start frontend
npm run dev

Backend 
# Navigate 
cd medtour-navigator/backend

# Create virtual environment 
python -m venv venv

# Activate virtual environment - Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend
uvicorn app.main:app --reload
