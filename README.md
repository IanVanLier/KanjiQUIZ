# TMW Vocab Trainer

A local web application for mastering Japanese vocabulary ranks through active recall, Romaji-to-Kana conversion, and automatic dictionary integration.

## 🚀 Setup & Installation

1.  **Install Python 3.8+**
2.  **Install Dependencies:**
    ```bash
    pip install flask genanki
    ```
3.  **Data Placement:**
    Place your `term_meta_bank_*.json` files in the same directory as `app.py`.
4.  **Run the App:**
    ```bash
    python app.py
    ```
5.  **Open in Browser:**
    Navigate to `http://127.0.0.1:5000`.

## 🕹️ How to Use

### Homepage
* **Rank Cards:** Displays stats for every rank from *Student* to *Owner*.
* **New Only:** Quiz words you haven't seen yet.
* **Failures Only:** Focused drill for words you got wrong.
* **Everything:** Standard review of the entire rank.

### Quiz Mode
* **Typing:** Type in Romaji; the app automatically converts it to Hiragana using **WanaKana.js**.
* **Submission:** Press **Enter** to check your answer.
* **Yomitan Integration:** Upon pressing Enter, the Kanji is automatically copied to your clipboard. If Yomitan's "Clipboard Monitor" is on, the definition will pop up instantly.

## 📊 Data & Resetting
* **Stats:** Progress is saved in `tmw_comprehensive_stats.json`.
* **Reset:** To wipe all stats and start over, delete the `tmw_comprehensive_stats.json` file.
* **Anki Export:** Use the homepage export button to generate an `.apkg` of your current failed words.

### Custom Word List
* **Custom Word List:** You can load your own .txt file (Kanji words 1 per line, non kanji words/kana only words are ignored), custom word quiz data is seperate from the TMW ranks.
* **Default:** Default is the Kaishi_1.5k_Words.txt which contains all the Kaishi words with Kanji
* **Import your own!:** you can import your own words from a jiten.moe export or an anki export to type them in the quiz. Press the DELETE CUSTOM BANK button and import your own text file.
* **Anki Export + TXT Export:** Custom Word List failures can be exported to anki or txt file

## 📋 Requirements
* **Flask:** Web server logic.
* **Genanki:** Anki deck generation.
* **Modern Browser:** Required for Clipboard API and WanaKana functionality.
