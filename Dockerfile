FROM python:3.11-slim

# 1️⃣ Installer dépendances Linux
RUN apt-get update && apt-get install -y \
    wget gnupg2 unzip curl xvfb ca-certificates \
    libnss3 libxss1 libasound2 libatk1.0-0 libcups2 libgtk-3-0 \
    libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxrandr2 libgbm1 \
    fonts-liberation libappindicator3-1 xdg-utils \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# 2️⃣ Ajouter le repo Chrome officiel et installer
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-linux-signing-key.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 3️⃣ Installer ChromeDriver correspondant (via apt)
RUN apt-get update && apt-get install -y chromium-chromedriver --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/lib/chromium-browser/chromedriver /usr/local/bin/chromedriver

# 4️⃣ Copier le code
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 5️⃣ Variables d'environnement pour Selenium headless
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV DISPLAY=:99

# 6️⃣ Lancer FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
