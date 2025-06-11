# Groovii: Generator playlist AI dla Spotify

> **Projekt uczelniany – stworzony w ramach zaliczenia zajęć**

Ta aplikacja Flask pozwala użytkownikom zalogować się przez Spotify, opisać swój nastrój, a następnie wykorzystuje Gemini AI Agents do wygenerowania spersonalizowanej playlisty z polubionych utworów. Aplikacja analizuje teksty piosenek i w razie potrzeby uzupełnia playlistę rekomendacjami AI.

## Funkcje
- Logowanie przez Spotify OAuth (zawsze świeże, sesja czyszczona przy każdej wizycie na stronie głównej)
- Wprowadzanie nastroju/opisu przez użytkownika
- Pobieranie polubionych utworów użytkownika ze Spotify
- Wykorzystanie Gemini AI (przez Agno agent) do analizy i dopasowania utworów na podstawie tekstów piosenek (z Genius.com lub podobnych)
- Jeśli nie ma wystarczająco pasujących utworów, drugi agent AI rekomenduje dodatkowe prawdziwe utwory ze Spotify, wykluczając już użyte
- Tworzenie playlisty na koncie Spotify użytkownika
- Nowoczesny, spójny interfejs (wszystkie style w `static/style.css`)
- Poprawna obsługa przełączania konta Spotify dedykowanym przyciskiem
