INDIAN PROFESSIONAL RUMMY - ANDROID APK PROJECT
Created by @cd786hassan

IS PROJECT ME KYA HAI?
- Android APK banane ke liye ready web project
- www/index.html, www/style.css, www/app.js
- Capacitor configuration
- GitHub Actions workflow: .github/workflows/build-apk.yml
- Aapki updated Python file reference folder me bhi rakhi hai

APK BANANE KA AASAN TAREEQA (LUDO JAISA):
1. ZIP extract kijiye.
2. Is folder ke andar ki sab files GitHub repository me upload kijiye. .github folder bhi upload hona chahiye.
3. GitHub repository me Actions tab kholiye.
4. “Build Rummy Android APK” workflow select kijiye.
5. “Run workflow” dabaiye aur build complete hone dijiye.
6. Green successful run kholiye, neeche Artifacts me “Indian-Professional-Rummy-APK” download kijiye.
7. ZIP artifact extract karke app-debug.apk Android phone me install kijiye.

GAME NOTES:
- App offline chalne ke liye banaya gaya hai; game ko internet/account ki zaroorat nahi.
- Portrait/mobile layout, 1-3 computer opponents, Easy/Normal/Hard selection.
- 13-card deal, stock/discard, wild rank, printed Joker, groups highlighting, sorting, declaration checks, scoreboard, sound toggle.
- Original Python source ko reference/python_rummy_popup_creator_sound.py me rakha gaya hai.

IMPORTANT:
Yeh Tkinter Python file ka direct one-click conversion nahi hai. Android ke liye HTML/CSS/JavaScript interface aur game logic port ki gayi hai. APK build karne ke liye GitHub Actions internet use karega. App ka game offline chalega.

LATEST UPDATE: Table tray now displays each player’s latest discarded card (YOU and CPU players). WASTE remains the action to discard the selected card. The bottom action grid spans the full available width.
\nHTML/CSS/JAVASCRIPT WORKSPACE: open http://127.0.0.1:8000/web-editor. index.html, style.css and script.js auto-save together in web_workspace.\n