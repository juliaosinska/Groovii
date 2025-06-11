# Groovii: Generator playlist AI dla Spotify

> **Projekt uczelniany – stworzony w ramach zaliczenia zajęć**

Jest to symulacja produktu stworzonego przez pracownika Spotify w ramach działań marketingowych. Produkt zostałby udostępniony użytkownikom premium, aby zobrazować chęć podążania za trednami związanymi z użyciem AI. 

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

## Screenshoty
![1](https://github.com/user-attachments/assets/62e65447-177e-4b0e-8e1b-078434581587)
![2](https://github.com/user-attachments/assets/43c18d0f-3660-447d-92d0-2074c9236c27)
![3](https://github.com/user-attachments/assets/47345a5c-7906-449d-89ec-d0fbeff92076)
