import logging
import re
import statistics
import webbrowser
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from PIL import Image, ImageTk
from io import BytesIO
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pyperclip
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import datetime
import time
import threading
import json
import os
import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Abilita il supporto per il DPI per-monitor su Windows 8.1 o superiore

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logger = logging.getLogger("logger")
logger.setLevel(logging.WARNING)
logger_handler = logging.FileHandler(os.path.join(log_dir, "logger.log"))
logger_handler.setFormatter(    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(logger_handler)


def load_products():
    """
    Carica i dati dei prodotti da file e avvia il monitoraggio per ogni prodotto
    """
    global products, products_to_view

    if os.path.exists(products_file):
        try:
            with open(products_file, "r") as file:
                products = json.load(file)

                # Controllo validità dei dati estratti
                for name in products:
                    if not isinstance(products[name], dict):
                        raise Exception("Ogni elemento nel file JSON dei dati prodotti deve essere un dizionario")
                    
                    url = products[name].get("url")

                    if not url:
                        raise Exception("Ogni prodotto deve avere un 'url'")
                    
                    # Avvio monitoraggio del prodotto estratto
                    start_tracking(name, url)

                # Aggiornamento prodotti da visualizzare sulla TreeView
                products_to_view = products

                logger.info("Dati dei prodotti caricati correttamente")
        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati prodotti: {e}")
            messagebox.showerror("Attenzione", "Errore durante il caricamento dei dati prodotti")
            exit()
    else:
        try:
            # Crea il file con un dizionario vuoto
            with open(products_file, "w") as file:
                json.dump({}, file)
            
                logger.warning(f"File dei dati prodotti '{products_file}' non trovato, creato nuovo file vuoto")
                messagebox.showwarning("Attenzione", f"File dei dati prodotti '{products_file}' non trovato\nCreato nuovo file vuoto")
        except Exception as e:
            logger.error(f"Errore durante la creazione del file dei dati prodotti: {e}")
            messagebox.showerror("Attenzione", "Errore durante la creazione del file dei dati prodotti")
            exit()


def save_products():
    """
    Salva i dati dei prodotti su file
    """
    global products_to_view

    # Aggiornamento prodotti da visualizzare sulla TreeView
    products_to_view = products

    try:
        # Salvataggio su file
        with open(products_file, "w") as file:
            json.dump(products, file, indent=4)

        logger.info("Dati prodotti salvati con successo")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati prodotti: {e}")


def load_emails():
    """
    Carica i dati delle email da file e avvia il monitoraggio per ogni prodotto
    """
    global emails

    if os.path.exists(emails_file):
        try:
            with open(emails_file, "r") as file:
                lines = file.readlines()
            
            emails = [line.strip() for line in lines]

            logger.info("Email caricate correttamente")
        except Exception as e:
            logger.error(f"Errore durante il caricamento delle email: {e}")
            messagebox.showerror("Attenzione", "Errore durante il caricamento delle email")
            exit()
    else:
        try:
            with open(emails_file, "w") as file:
                pass
            
                logger.warning(f"File delle email '{emails_file}' non trovato, creato nuovo file vuoto")
                messagebox.showwarning("Attenzione", f"File delle email '{emails_file}' non trovato\nCreato nuovo file vuoto")
        except Exception as e:
            logger.error(f"Errore durante la creazione del file delle email: {e}")
            messagebox.showerror("Attenzione", "Errore durante la creazione del file delle email")
            exit()


def save_emails():
    """
    Salva i dati delle email su file
    """
    try:
        # Salvataggio su file
        with open(emails_file, 'w') as file:
            for line in emails:
                file.write(line + '\n')

        logger.info("Email salvate con successo")
    except Exception as e:
        logger.error(f"Errore nel salvataggio delle email: {e}")


def load_prices():
    """
    Carica i dati di monitoraggio dei prezzi da file
    """
    global prices

    if os.path.exists(prices_file):
        try:
            with open(prices_file, "r") as file:
                prices = json.load(file)

                # Controllo validità dei dati estratti
                for name in prices:
                    if not isinstance(prices[name], list):
                        raise Exception("Ogni elemento nel file JSON dei dati monitoraggio prezzi deve essere una lista")
                    
                logger.info("Dati monitoraggio prezzi caricati correttamente")
        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati monitoraggio prezzi: {e}")
            messagebox.showerror("Attenzione","Errore durante il caricamento dei dati monitoraggio prezzi")
            exit()
    else:
        try:
            # Crea il file con un dizionario vuoto
            with open(prices_file, "w") as file:
                json.dump({}, file)
            
            logger.warning(f"File dei dati monitoraggio prezzi '{prices_file}' non trovato, creato nuovo file vuoto")
            messagebox.showwarning("Attenzione", f"File dei dati monitoraggio prezzi '{prices_file}' non trovato\nCreato nuovo file vuoto.")
        except Exception as e:
            logger.error(f"Errore durante la creazione del file dei dati monitoraggio prezzi: {e}")
            messagebox.showerror("Attenzione", "Errore durante la creazione del file dei dati monitoraggio prezzi")
            exit()


def save_prices():
    """
    Salva i dati di monitoraggio dei prezzi dei prodotti su file
    """
    try:
        # Salvataggio su file
        with open(prices_file, "w") as file:
            json.dump(prices, file, indent=4)

        logger.info("Dati di monitoraggio dei prezzi dei prodotti salvati con successo")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati di monitoraggio dei prezzi dei prodotti: {e}")


def save_price(name, price):
    """
    Salva i dati di monitoraggio del prezzo per un prodotto su file
    """
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price_entry = {"price": price, "date": current_time}

    # Crea la chiave del dizionario qual'ora non esistesse
    if name not in prices:
        prices[name] = []

    # Aggiunta del nuovo prezzo allo storico dei prezzi del prodotto
    prices[name].append(price_entry)

    # Salvataggio su file
    try:
        with open(prices_file, "w") as file:
            json.dump(prices, file, indent=4)

        logger.info(f"Salvato aggiornamento prezzo per {name}: {price}€ al {current_time}")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati monitoraggio prezzi: {e}")


def check_and_save_new_emails():
    """
    Controlla le email associate ai prodotti e aggiorna la lista delle email usate come cronologia
    """
    global emails

    for name in products:
        emails_and_thresholds = products[name]['emails_and_thresholds']

        for email in emails_and_thresholds:
            if email not in emails:
                emails.append(email)

    save_emails()


def open_images_folder():
    """
    Funzione per aprire la cartella immagini
    """
    if os.path.exists(images_dir):
        os.startfile(images_dir)  # Su Windows
    else:
        logger.error("La cartella delle immagini non esiste")
        tk.messagebox.showerror("Errore", "La cartella delle immagini non esiste!")


def clean_products_and_prices_history():
    """
    Rimuove dalla cronologia di monitoraggio dei prezzi tutti i prodotti che non sono più osservati
    """
    continueCleanProductsAndPricesHistory = messagebox.askyesno(
                        "Pulizia cronologia",
                        "Sei sicuro di voler rimuovere dalla cronologia i prodotti non osservati e i relativi prezzi memorizzati?" 
                    )

    # Verifica risposta
    if continueCleanProductsAndPricesHistory:
        name_products = products.keys()
        name_prices = list(prices.keys())

        for name_price in name_prices:
            if name_price not in name_products:
                del prices[name_price]

        save_prices()


def clean_emails_history():
    """
    Ripulisce la lista delle email, rimuovendo quelle non più associate a prodotti monitorati
    """
    global emails

    continueCleanEmailsHistory = messagebox.askyesno(
                        "Pulizia cronologia",
                        "Sei sicuro di voler rimuovere dalla cronologia le email non più utilizzate?" 
                    )

    # Verifica risposta
    if continueCleanEmailsHistory:
        emails.clear()

        for name in products:
            emails_and_thresholds = products[name]['emails_and_thresholds']

            for email in emails_and_thresholds:
                if email not in emails:
                    emails.append(email)
        
        save_emails()


def center_window(window):
    """
    Centra una finestra Tkinter sullo schermo
    """
    window.update_idletasks()

    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def open_about_dialog():
    """
    Crea una finestra modale con informazioni personali e di release.
    """
    # Creazione della finestra modale
    about_dialog = tk.Toplevel(root)
    about_dialog.title("Info")
    about_dialog.resizable(False, False)
    about_dialog.configure(padx=50, pady=5)
    about_dialog.grab_set()

    # Label con il nome dell'utente
    name_label = tk.Label(about_dialog, text="Vincenzo Salvati", font=("Arial", 14, "bold"))
    name_label.pack(pady=10)

    # Label con il numero di versione/release
    release_label = tk.Label(about_dialog, text="Versione: 3.4.0", font=("Arial", 12))
    release_label.pack(pady=5)

    # Label con un eventuale numero di release successiva
    release_note_label = tk.Label(about_dialog, text="Ultima release: 13 ottobre 2024", font=("Arial", 10))
    release_note_label.pack(pady=5)

    # Pulsante per chiudere la finestra modale
    close_button = ttk.Button(about_dialog, text="Chiudi", command=about_dialog.destroy)
    close_button.pack(pady=15)

    center_window(about_dialog)


def reset_filters(reset_search_bar=True):
    """
    Reimposta i filtri e ordina i prodotti per data di ultima modifica
    """
    global products_to_view, sort_state

    # Reimposta lo stato dell'ordinamento
    sort_state = {"column": None, "order": 0}

    # Elenco dei prodotti da visualizzare come lista di tuple
    list_products_to_view = list(products_to_view.items())

    # Mappa delle funzioni di ordinamento per ciascuna colonna
    column_key_map = {
        "Nome": lambda item: item[0].lower(),
        "URL": lambda item: item[1]["url"].lower(),
        "Prezzo": lambda item: item[1]["price"] if isinstance(item[1]["price"], (int, float)) else float("inf"),
        "Notifica": lambda item: item[1]["notify"],
        "Timer": lambda item: item[1]["timer"],
        "Timer Aggiornamento [s]": lambda item: item[1]["timer_refresh"],
        "Data Inserimento": lambda item: item[1]["date_added"],
        "Data Ultima Modifica": lambda item: item[1]["date_edited"],
    }

    # Ordinamento dei prodotti per data di ultima modifica
    list_products_to_view.sort(key=column_key_map["Data Ultima Modifica"])

    # Aggiornamento ordine dei prodotti da visualizzare
    products_to_view = {name: details for name, details in list_products_to_view}

    # Ripristino delle intestazioni delle colonne nella TreeView
    for column in columns:
        products_tree.heading(column, text=column, anchor="center")

    # Reset della barra di ricerca quando richiesto
    if reset_search_bar:
        search_entry.delete(0, tk.END)
        search_entry.insert(0, placeholder_text)
        search_entry.config(fg='grey')


def calculate_suggestion(all_prices, current_price, price_average, price_minimum, price_maximum):
    """
    Fornisce suggerimenti sul prezzo attuale basati su statistiche storiche
    """
    if not isinstance(current_price, (int, float)):
        return "Prezzo attuale inesistente: aggiorna il prodotto o cambia il suo url", "black"
    elif all(x == all_prices[0] for x in all_prices):
        return "Ad oggi non sono state rilevate variazioni di prezzo", "blue"
    elif current_price <= price_minimum:
        return "Ottimo momento per comprare!", "green"
    elif current_price < price_average * 0.9:
        return "Prezzo inferiore alla media, buon momento per comprare", "green"
    elif current_price >= price_maximum:
        return "Prezzo alto rispetto alla storia, considera di aspettare una riduzione", "red"
    else:
        return "Prezzo nella media, considera se hai bisogno del prodotto ora", "#FFA500"


def calculate_statistics(all_prices, current_price):
    """
    Calcola le statistiche sui prezzi storici: media, minimo e massimo
    """
    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = current_price
    
    return average_price, price_minimum, price_maximum


def send_notification_and_email(name, previous_price, current_price):
    """
    Invia una notifica e una e-mail di aggiornamento del prezzo per un prodotto
    """
    def load_config():
        """
        Carica la configurazione per l'invio di email e notifiche Telegram da file
        """
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as file:
                    config = json.load(file)
                    
                    return (config["sender_email"], config["sender_password"], config["receiver_email"], config["url_telegram"], config["chat_id_telegram"])
            except Exception as e:
                logger.error(f"Errore nel caricamento del file di configurazione: {e}")
                messagebox.showerror("Attenzione", "Errore nel caricamento del file di configurazione")
                exit()
        else:
            logger.error(f"File di configurazione '{config_file}' non trovato")
            messagebox.showerror("Attenzione", f"File di configurazione '{config_file}' non trovato")
            exit()
    
    def send_email(subject, body, image_path, email_to_notify):
        """
        Invia un'email con l'oggetto e il corpo al destinatario
        """
        # Carica le credenziali email mittente
        from_email, from_password, _, _, _ = load_config()

        # Crea il messaggio email
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = email_to_notify
        msg["Subject"] = subject
        
        # Aggiungi il corpo del messaggio
        msg.attach(MIMEText(body, 'html'))

        # Aggiungi l'immagine se presente
        if image_path and os.path.isfile(image_path):
            with open(image_path, 'rb') as img:
                image = MIMEImage(img.read())
                image.add_header('Content-ID', '<image1>')
                msg.attach(image)

        try:
            server = smtplib.SMTP("smtp.gmail.com", 587) # Imposta connessione al server SMTP
            server.starttls() # Abilita connessionE TLS
            server.login(from_email, from_password)
            server.sendmail(from_email, email_to_notify, msg.as_string())
            server.quit()
        except Exception as e:
            logger.error(f"Impossibile inviare l'email: {e}")

    def send_default_notification(subject, body, body_email, image_path):
        """
        Invia una email e una notifica Telegram al desinatario di default
        """
        # Carica i contatti del destinatario di default
        _, _, default_recipient_email, default_url_telegram, default_chat_id_telegram = load_config()

        # Invia email
        send_email(subject, body_email, image_path, default_recipient_email)

        try:
            # Prepara payload per Telegram
            payload = {"chat_id": default_chat_id_telegram, "text": body}

            # Invia notifica Telegram
            response = requests.post(default_url_telegram, data=payload)

            # Controllo riuscita dell'invio
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Impossibile inviare il messaggio Telegram: {e}")
        
    # Calcola statistiche sui prezzi dello storico del prodotto
    historical_prices = prices.get(name, [])
    all_prices = [entry["price"] for entry in historical_prices if isinstance(entry["price"], (int, float))]
    average_price, price_minimum, price_maximum = calculate_statistics(all_prices, current_price)

    # Calcolo del suggerimento per l'utente basato sui prezzi dello storico del prodotto
    text_suggestion, _ = calculate_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)

    # Prepara l'oggetto e il corpo della notifica
    subject = "Prezzo in calo!"
    if average_price == price_minimum == price_maximum:
        body = (
            f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n"
            + "Dettagli:\n\t- Primo ribasso del prezzo rilevato\n\nNon ho abbastanza dati nello storico del prodotto per fornire un suggerimento sulla validità dell'acquisto\n\n"
            + f"Acquista ora: {products[name]['url']}"
        )
        body_email = (
                f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.<br><br>"
                + "Dettagli:<br>\t- Primo ribasso del prezzo rilevato<br><br>"
                + "Non ho abbastanza dati nello storico del prodotto per fornire un suggerimento sulla validità dell'acquisto.<br><br>"
                + f"Acquista ora: <a href='{products[name]['url']}'>clicca qui</a><br><br>"
        )
    else:
        body = (
            f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n"
            + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
            + f"Acquista ora: {products[name]['url']}"
            )
        body_email = (
                f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.<br><br>"
                + f"Dettagli:<br>\t- Prezzo medio: {average_price}€<br>\t- Prezzo minimo storico: {price_minimum}€<br>\t- Prezzo massimo storico: {price_maximum}€<br><br>"
                + f"{text_suggestion}<br><br>"
                + f"Acquista ora: <a href='{products[name]['url']}'>clicca qui</a><br><br>"
        )
    
    image_path = products[name].get('image')

    if image_path and os.path.isfile(image_path):
        body_email += f"<img src='cid:image1'>"

    # Invio notifica telegram
    if current_price < previous_price:
        send_default_notification(subject, body, body_email, image_path)

    # Controllo delle soglie e invio delle e-mail
    for email, threshold in products[name]["emails_and_thresholds"].items():
        value_to_compare = previous_price
        subject_to_send = subject
        body_to_send = body_email

        # Tenere conto della soglia nel caso in cui fosse settata
        if threshold != 0.0:
            value_to_compare = threshold
            subject_to_send = "Prezzo inferiore alla soglia indicata!"
            body_to_send = (
                        f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.<br>"
                        + f"Il costo attuale è {current_price}€.<br><br>"
                        + f"Dettagli:<br>\t- Prezzo medio: {average_price}€<br>\t- Prezzo minimo storico: {price_minimum}€<br>\t- Prezzo massimo storico: {price_maximum}€<br><br>"
                        + f"{text_suggestion}<br><br>"
                        + f"Acquista ora: <a href='{products[name]['url']}'>clicca qui</a><br><br>"
            )

            if image_path and os.path.isfile(image_path):
                body_to_send += f"<img src='cid:image1'>"

        # Invio e-mail in caso di diminuizione del prezzo o diminuizione oltre la soglia
        if current_price < value_to_compare:
            send_email(subject_to_send, body_to_send, image_path, email)


def get_last_price(name):
    """
    Restituisce l'ultimo prezzo salvato per un determinato prodotto
    """
    if name in prices:
        last_entry = max(prices[name], key=lambda x: x["date"])

        return last_entry["price"]
    else:
        return None
    

def get_price(url):
    """
    Estrae il prezzo di un prodotto da una pagina Amazon
    """
    # Definizione dell'header per emulare un browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9",
    }

    try:
        # Esecuzione richiesta HTTP
        response = requests.get(url, headers=headers)

        # Verifica errori nella risposta
        response.raise_for_status()

        # Parsing del contenuto HTML della risposta
        soup = BeautifulSoup(response.content, "html.parser")

        # Ricerca titolo del prodotto
        title_element = soup.find("span", id="productTitle")

        if title_element is None:
            raise ValueError("Titolo del prodotto non trovato")
        
        title_container = title_element.find_parent()

        # Trova il prezzo del prodotto sotto al titolo
        price_element = title_container.find_next("span", class_="aok-offscreen")

        if price_element is None:
            raise ValueError("Elemento prezzo non trovato sotto il titolo")
        
        # Estrae e pulisce il testo del prezzo
        price_text = price_element.get_text().strip()

        # Verifica validità del prezzo
        price_is_valid = re.search(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?", price_text)

        if price_is_valid:
            price_value = price_is_valid.group(0).replace(".", "").replace(",", ".")

            return float(price_value)
        else:
            raise ValueError("Prezzo non trovato nel testo")
    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP di get_price: {e}")
        return None
    except Exception as e:
        logger.error(f"Errore in get_price: {e}")
        return None


def get_image(name):
    """
    Estrae il prezzo e la prima immagine di un prodotto da una pagina Amazon
    """
    # Definizione dell'header per emulare un browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9",
    }

    try:
        # Esecuzione richiesta HTTP
        response = requests.get(products[name]['url'], headers=headers)
        response.raise_for_status()

        # Parsing del contenuto HTML della risposta
        soup = BeautifulSoup(response.content, "html.parser")

        # Trova la prima immagine del prodotto
        image_element = soup.find("img", id="landingImage")
        if image_element is None:
            raise ValueError(f"Immagine di {name} non trovata")
        image_url = image_element['src']

        # Scarica l'immagine
        image_response = requests.get(image_url)
        image_response.raise_for_status()

        # Crea la directory se non esiste
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)

        # Salva l'immagine
        image = Image.open(BytesIO(image_response.content))
        image_path = os.path.join(images_dir, f"{name.replace(' ', '_')}.jpg")  # Limita la lunghezza del nome del file
        image.save(image_path)

        return image_path

    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP di get_image per il prodotto {name}: {e}")
        return products[name]['image'] if products[name]['image'] else None
    except Exception as e:
        logger.error(f"Errore in get_image per il prodotto {name}: {e}")
        return products[name]['image'] if products[name]['image'] else None


def start_tracking(name, url):
    """
    Avvia o riavvia il monitoraggio del prezzo di un prodotto
    """
    def track_loop(name, url):
        """
        Ciclo di monitoraggio del prezzo del prodotto
        """
        def check_price_and_notify(name, url):
            """
            Controlla il prezzo attuale e invia notifiche in caso di ribasso del prezzo
            """
            # Recupera il prezzo attuale
            current_price = get_price(url)

            if current_price is None:
                logger.warning(f"Non trovato il prezzo di {name} sulla pagina {url}")
                return
            
            # Verifica se le notifiche del prodotto sono attivate
            if products[name]["notify"]:
                # Recupera l'ultimo prezzo memorizzato del prodotto
                previous_price = get_last_price(name)
                
                if previous_price is None:
                    logger.warning(f"Non trovato il prezzo di {name} nelle liste")
                    return
                
                send_notification_and_email(name, previous_price, current_price)

            # Aggiornamento del prodotto
            products[name]["price"] = current_price

            save_price(name, products[name]["price"])
            save_products()

        # Ripeti il loop finchè l'evento non viene settato
        while not stop_events[name].is_set():
            products[name]["timer"] = time.time()

            # Aspetta il timer e verifica la condizione di uscita del loop
            if stop_events[name].wait(products[name]["timer_refresh"]):
                break  

            check_price_and_notify(name, url)

            # Resetta i filtri al seguito dell'aggiornamento del prezzo
            reset_filters()

        # Rimuove l'evento di stop del thread al termine del loop
        del stop_events[name]

        logger.info(f"Monitoraggio di '{name}' fermato")

    global threads, stop_events

    # Ferma un eventuale monitoraggio del prodotto qual'ora fosse già attivo
    if name in threads and threads[name].is_alive():
        logger.info(f"Fermando il monitoraggio precedente di '{name}'...")

        stop_events[name].set() # Segnala al thread corrente di fermarsi
        threads[name].join(timeout=1) # Aspetta che il thread corrente termini

    # Crea il thread di monitoraggio e il suo evento di stop
    threads[name] = threading.Thread(target=track_loop, args=(name, url,), daemon=True,)
    stop_events[name] = threading.Event()
    
    # Avvio del monitoraggio del prodotto
    threads[name].start()

    logger.info(f"Avviato il monitoraggio per '{name}' ({url}) con un nuovo timer")


def block_root():
    """
    Blocca il refresh della Root e qualsiasi interazione essa
    """
    set_periodic_refresh_root(False)

    for window in root.winfo_children():
        try:
            window.attributes("-disabled", True)
        except:
            pass
    root.wm_attributes("-disabled", True)


def unlock_root():
    """
    Sblocca il refresh della Root e l'interazione essa
    """
    set_periodic_refresh_root()

    for window in root.winfo_children():
        try:
            window.attributes("-disabled", False)
        except:
            pass
    root.attributes("-disabled", False)


def open_advanced_dialog(parent_dialog):
    """
    Apre il dialogo avanzato per aggiungere soglie di notifica via email e modifica del timer di aggiornamento
    """
    def is_valid_email(email):
        # Espressione regolare per validare il formato dell'email
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return re.match(email_regex, email) is not None
    
    def close_advanced_dialog(advanced_dialog, parent_dialog):
        advanced_dialog.grab_release()  # Rilascia il grab
        parent_dialog.grab_set()  # Riapplica il grab alla finestra principale se necessario
        advanced_dialog.destroy()

    def add_email_threshold():
        """
        Aggiunta di email e soglia di prezzo
        """
        email = email_entry.get().strip().lower()
        threshold = threshold_entry.get().strip()

        if not email:
            messagebox.showwarning("Attenzione", "Compila l'email!")
            return
        
        if not is_valid_email(email):
            messagebox.showwarning("Attenzione", "Inserire una e-mail corretta!")
            return
        
        # Notifica senza soglia specifica
        if not threshold:
            threshold = 0.0

        try:
            threshold = float(threshold)

            if threshold < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")
            return
        
        # Verifica esistenza di una e-mail già associata al prodotto
        if email in emails_and_thresholds:
            messagebox.showwarning("Attenzione", "L'email è già presente nella tabella")
            return
        
        emails_and_thresholds[email] = threshold

        # Aggiornamento della tabella dopo l'inserimento
        update_email_and_threshold_tree()

        # Svuota i campi
        email_entry.delete(0, "end")
        threshold_entry.delete(0, "end")
    
    def is_valid_timer(input_value):
        """
        Validazione dell'input del timer, accettando solo numeri positivi o stringhe vuote
        """
        return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

    def modify_threshold():
        """
        Modifica la soglia di notifica per l'email selezionata
        """
        email = email_and_threshold_tree.selection()[0]

        # Inserimento della nuova soglia
        new_threshold = simpledialog.askstring("Modifica Soglia", f"Soglia di notifica per '{email}':")
        new_threshold = new_threshold.replace(" ", "")

        if new_threshold == "":
            new_threshold = 0.0

        try:
            emails_and_thresholds[email] = float(new_threshold)

            # Aggiornamento della tabella dopo la modifica
            update_email_and_threshold_tree()
        except:
            messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")

    def remove_email():
        """
        Rimuove l'email selezionata dalla tabella
        """
        global hovered_row_email_and_threshold_tree

        email = email_and_threshold_tree.selection()[0]

        del emails_and_thresholds[email]

        hovered_row_email_and_threshold_tree = None
        
        # Aggiornamento della tabella dopo la rimozione
        update_email_and_threshold_tree()

    def click_email_and_threshold_tree(event):
        """
        Selezione riga con il tasto sinistro del mouse
        Deseleziona tutte le righe se si seleziona qualcosa di diverso da una riga
        """
        def hide_suggestions(event):
            """
            Nasconde il frame che contiene la `listbox_suggestions`
            """
            if event.widget != email_entry:
                listbox_frame.place_forget()
            
            if event.widget == listbox_suggestions:
                email_entry.focus_set()
                
        hide_suggestions(event)

        rows_in_email_and_threshold_tree = email_and_threshold_tree.get_children()
        selected_email_and_threshold = email_and_threshold_tree.selection()

        # Identifica l'elemento cliccato (basato sulla posizione y del click)
        identified_email_and_threshold_index = email_and_threshold_tree.identify_row(event.y)

        # Seleziona o deseleziona una riga in base a se è stato cliccato o meno
        if identified_email_and_threshold_index in rows_in_email_and_threshold_tree:
            row_index = rows_in_email_and_threshold_tree.index(identified_email_and_threshold_index)
            
            email_and_threshold_tree.selection_remove(*selected_email_and_threshold)
            email_and_threshold_tree.selection_add(rows_in_email_and_threshold_tree[row_index])
        else:
            email_and_threshold_tree.selection_remove(*selected_email_and_threshold)

    def update_suggestions(*args):
        """
        Aggiorna i suggerimenti nella `listbox_suggestions` in base al testo inserito in `email_entry`
        """
        typed_text = email_entry_var.get().strip().lower()

        # Reset della lista di suggerimenti
        listbox_suggestions.delete(0, tk.END)

        if typed_text:
            # Ricerca dei nomi dei prodotti che contengono il testo digitato
            matching_suggestions_start = sorted([email for email in emails if email.lower().startswith(typed_text)])
            matching_suggestions_contain = sorted([email for email in emails if typed_text in email.lower() and not email.lower().startswith(typed_text)])
            matching_suggestions = matching_suggestions_start + matching_suggestions_contain

            if len(matching_suggestions) == 0:
                listbox_frame.place_forget()
            else:
                # Aggiunta dei suggerimenti alla lista dei suggerimenti
                for suggestion in matching_suggestions:
                    listbox_suggestions.insert(tk.END, suggestion)

                # Impostazione altezza massima della lista dei suggerimenti
                listbox_suggestions.config(height=min(len(matching_suggestions), 5))

                # Posiziona il frame che contiene la lista dei suggerimenti sotto il campo di input
                listbox_frame.place(x=email_entry.winfo_x(), y=email_entry.winfo_y() + email_entry.winfo_height(), anchor="nw")
                
                # Solleva la lista dei suggerimenti in cima a tutti gli altri widget
                listbox_suggestions.lift()
        else:
            # Nasconde la lista dei suggerimenti qual'ora non venga digitato alcun testo
            listbox_frame.place_forget()

    def on_select_suggestion(event=None):
        """
        Selezione del suggerimento e trascrizione in `email_entry`
        """
        selected_suggestion_index = listbox_suggestions.curselection()

        if selected_suggestion_index:
            selected_suggestion_name = listbox_suggestions.get(selected_suggestion_index[0])

            # Reset e riempimento in `email_entry`
            email_entry.delete(0, tk.END)
            email_entry.insert(0, selected_suggestion_name)

            advanced_dialog.focus_set()

    def show_email_and_threshold_menu(event):
        """
        Mostra un menu contestuale per modificare una soglia o rimuovere un'e-mail
        """
        # Identifica l'e-mail cliccata (basato sulla posizione y del click)
        identified_email = email_and_threshold_tree.identify_row(event.y)

        if not identified_email:
            return
        
        # Selezione dell'e-mail cliccata
        email_and_threshold_tree.selection_set(identified_email)

        # Mostra menu contestuale
        email_threshold_menu.post(event.x_root, event.y_root)

    def on_hover_email_and_threshold_tree(event):
        """
        Evidenzia le righe sul TreeView al passaggio del mouse
        """
        global hovered_row_email_and_threshold_tree

        # Identifica la riga sopra la quale si trova il mouse
        row_id = email_and_threshold_tree.identify_row(event.y)

        # Se il mouse è sopra una riga e non è la stessa già evidenziata
        if row_id and row_id != hovered_row_email_and_threshold_tree:
            # Resetta il colore della riga precedentemente evidenziata
            if hovered_row_email_and_threshold_tree:
                email_and_threshold_tree.item(hovered_row_email_and_threshold_tree, tags=())

            # Assegna il tag "hover" alla nuova riga
            email_and_threshold_tree.item(row_id, tags=("hover",))

            hovered_row_email_and_threshold_tree = row_id

        # Se il mouse non è sopra una riga, resetta l'hover
        elif not row_id and hovered_row_email_and_threshold_tree:
            email_and_threshold_tree.item(hovered_row_email_and_threshold_tree, tags=())
            hovered_row_email_and_threshold_tree = None

    def on_timer_change(*args):
        """
        Gestistione del cambiamento del valore del timer
        """
        global timer_refresh

        value = timer_entry.get()

        if value.isdigit():
            timer_refresh = int(value)
        else:
            timer_refresh = 0

        if timer_refresh == 0:
            timer_refresh = 1800 # Valore di default
            timer_entry.delete(0, "end")
            timer_entry.insert(0, "1800")

    def update_email_and_threshold_tree():
        """
        Aggiorna la tabella che mostra le e-mail e le soglie
        """
        # Svuota tabella delle e-mail e dei threshold
        email_and_threshold_tree.delete(*email_and_threshold_tree.get_children())

        # Riempi la tabella delle e-mail e dei threshold con i valori aggiornati
        for key, value in sorted(emails_and_thresholds.items()):
            email_and_threshold_tree.insert("", "end", iid=key, values=(key, str(value) + "€" if value != 0.0 else "Non definita"))

    # Configurazione del dialogo per le opzioni avanzate
    advanced_dialog = tk.Toplevel(root)
    advanced_dialog.protocol("WM_DELETE_WINDOW", lambda: close_advanced_dialog(advanced_dialog, parent_dialog))
    advanced_dialog.title("Aggiungi e-mail e soglia notifica")
    advanced_dialog.resizable(False, False)
    advanced_dialog.transient(parent_dialog)
    advanced_dialog.grab_set()
    
    container = ttk.Frame(advanced_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    # E-mail
    ttk.Label(container, text="E-mail:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    email_entry_var = tk.StringVar()
    email_entry_var.trace_add("write", update_suggestions) # Regola per eseguire una funzione quando il contenuto di un widget cambia

    email_entry = ttk.Entry(container, width=50, textvariable=email_entry_var, font=("Arial", 10))
    email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # Lista suggerimenti
    listbox_frame = ttk.Frame(advanced_dialog)
    listbox_frame.place_forget()

    listbox_suggestions = tk.Listbox(listbox_frame, width=50)
    listbox_suggestions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox_suggestions.yview)
    scrollbar.pack(side="right", fill="y")
    listbox_suggestions.config(yscrollcommand=scrollbar.set)

    # Soglia
    ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    # Frame per Entry e messaggio
    threshold_frame = ttk.Frame(container)
    threshold_frame.grid(row=1, column=1, padx=10, pady=10, sticky="w")

    threshold_entry = ttk.Entry(threshold_frame, width=15, font=("Arial", 10), validate="key", validatecommand=(root.register(lambda s: s.isdigit() or s in [".", "-"]), "%S"))
    threshold_entry.pack(side="left")

    ttk.Label(threshold_frame, text="Inserisci un valore numerico oppure lascia vuoto", font=("Arial", 8, "italic")).pack(side="left", padx=(10, 0))

    # Pulsante
    add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
    add_button.grid(row=2, column=0, columnspan=2, pady=(10, 20), sticky="e")

    # Lista delle e-mail e delle soglie
    email_and_threshold_tree = ttk.Treeview(container, columns=("Email", "Soglia"), show="headings")
    email_and_threshold_tree.grid(row=3, column=0, columnspan=2, sticky="nsew")

    email_and_threshold_tree.heading("Email", text="Email")
    email_and_threshold_tree.heading("Soglia", text="Soglia")

    scrollbar_vertical = ttk.Scrollbar(container, orient="vertical", command=email_and_threshold_tree.yview)
    scrollbar_vertical.grid(row=3, column=2, sticky="ns")

    scrollbar_horizontal = ttk.Scrollbar(container, orient="horizontal", command=email_and_threshold_tree.xview)
    scrollbar_horizontal.grid(row=4, column=0, columnspan=2, sticky="ew")

    email_and_threshold_tree.configure(yscrollcommand=scrollbar_vertical.set, xscrollcommand=scrollbar_horizontal.set)
    email_and_threshold_tree.tag_configure("hover", background="#cceeff")

    # Timer aggiornamento
    ttk.Label(container, text="Timer [s]:").grid(row=5, column=0, padx=10, pady=10, sticky="we")
    
    timer_entry = ttk.Entry(container, width=20, font=("Arial", 10), validate="key", validatecommand=(root.register(is_valid_timer), "%P"))
    timer_entry.grid(row=5, column=1, padx=10, pady=10, sticky="w")
    timer_entry.insert(0, timer_refresh)

    # Menu tasto destro        
    email_threshold_menu = tk.Menu(advanced_dialog, tearoff=0)
    email_threshold_menu.add_command(label="Modifica Soglia", command=modify_threshold)
    email_threshold_menu.add_command(label="Rimuovi Email", command=remove_email)

    # Definizione eventi widget
    advanced_dialog.bind("<Button-1>", lambda event: click_email_and_threshold_tree(event))

    email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))
    email_entry.bind("<FocusIn>", update_suggestions)

    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)

    threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

    email_and_threshold_tree.bind("<Button-3>", show_email_and_threshold_menu)
    email_and_threshold_tree.bind("<Motion>", on_hover_email_and_threshold_tree)

    timer_entry.bind("<KeyRelease>", on_timer_change)
    timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))

    # Mostra eventuali e-mail e relative soglie nella tabella
    update_email_and_threshold_tree()

    center_window(advanced_dialog)

    # La dimensione delle colonne può essere definita solo dopo aver creato il dialog
    available_width = email_and_threshold_tree.winfo_width()
    email_and_threshold_tree.column("Email", width=int(available_width * 0.8), stretch=False)
    email_and_threshold_tree.column("Soglia", width=int(available_width * 0.2), anchor="center", stretch=False)


def open_add_product_dialog():
    """
    Apre una finestra di dialogo per aggiungere un prodotto, con funzionalità avanzate per gestire notifiche via email e soglie
    """
    def hide_suggestions(event=None):
        """
        Nasconde il frame che contiene la `listbox_suggestions`
        """
        if event.widget != name_entry:
            listbox_frame.place_forget()
        
        if event.widget == listbox_suggestions:
            name_entry.focus_set()

    def update_suggestions(*args):
        """
        Aggiorna i suggerimenti nella `listbox_suggestions` in base al testo inserito in `name_entry`
        """
        typed_text = name_entry_var.get().strip().lower()

        # Reset della lista di suggerimenti
        listbox_suggestions.delete(0, tk.END)

        if typed_text:
            # Ricerca dei nomi dei prodotti che contengono il testo digitato
            matching_suggestions_start = sorted([name for name in prices.keys() if name.lower().startswith(typed_text)])
            matching_suggestions_contain = sorted([name for name in prices.keys() if typed_text in name.lower() and not name.lower().startswith(typed_text)])
            matching_suggestions = matching_suggestions_start + matching_suggestions_contain

            if len(matching_suggestions) == 0:
                listbox_frame.place_forget()
            else:
                # Aggiunta dei suggerimenti alla lista dei suggerimenti
                for suggestion in matching_suggestions:
                    listbox_suggestions.insert(tk.END, suggestion)

                # Impostazione altezza massima della lista dei suggerimenti
                listbox_suggestions.config(height=min(len(matching_suggestions), 5))

                # Posiziona il frame che contiene la lista dei suggerimenti sotto il campo di input
                listbox_frame.place(x=name_entry.winfo_x(), y=name_entry.winfo_y() + name_entry.winfo_height(), anchor="nw")
                
                # Solleva la lista dei suggerimenti in cima a tutti gli altri widget
                listbox_suggestions.lift()
        else:
            # Nasconde la lista dei suggerimenti qual'ora non venga digitato alcun testo
            listbox_frame.place_forget()

    def on_select_suggestion(event=None):
        """
        Selezione del suggerimento e trascrizione in `name_entry`
        """
        selected_suggestion_index = listbox_suggestions.curselection()

        if selected_suggestion_index:
            selected_suggestion_name = listbox_suggestions.get(selected_suggestion_index[0])

            # Reset e riempimento in `name_entry`
            name_entry.delete(0, tk.END)
            name_entry.insert(0, selected_suggestion_name)

            add_product_dialog.focus_set()

    def add_product(name, url):
        """
        Aggiunge i dettagli di un prodotto
        """
        if not name or not url:
            messagebox.showwarning("Attenzione", "Compila tutti i campi!")
            return False
        
        for existing_name in products:
            if name == existing_name:
                messagebox.showwarning("Attenzione", "Il nome del prodotto è già presente!\nCambia il nome")
                return False
            
            if url == products[existing_name]["url"]:
                messagebox.showwarning("Attenzione", "Questo prodotto è già in monitoraggio!\nCambia url")
                return False

        # Blocco della Root durante l'aggiunta del prodotto
        block_root()

        # Ricerca prezzo
        current_price = get_price(url)

        if current_price is None:
            current_price = "aggiorna o verifica l'URL: - "
            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\naggiorna o verifica l'URL")
        else:
            # Verifica se una delle sogle impostate è più alta del prezzo corrente
            for threshold in emails_and_thresholds.values():
                if threshold > current_price:
                    continueToAddProduct = messagebox.askyesno(
                        "Conferma soglia",
                        "La soglia di notifica che hai inserito è più alta del prezzo attuale.\nInserire comunque il prodotto con questa specifica?" 
                        if len(emails_and_thresholds) > 1 
                        else "Una delle soglie di notifica che hai inserito è più alta del prezzo attuale.\nInserire comunque il prodotto con questa specifica?" 
                    )

                    # Verifica risposta
                    if not continueToAddProduct:
                        # Sblocca la Root per consentire ulteriori interazioni
                        unlock_root()

                        # Consenti la modifica della soglia
                        open_advanced_dialog()
                        return
                    
                    # E' inutile controllare altro se non importa che una delle soglie sia più alta del prezzo corrente
                    break

        # Crea il nuovo prodotto da aggiungere alla lista
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        products[name] = {
            "url": url,
            "price": current_price,
            "notify": notify.get(),
            "timer": time.time(),
            "timer_refresh": timer_refresh,
            "date_added": now,
            "date_edited": now,
            "emails_and_thresholds": emails_and_thresholds,
            "image": ""
        }
        products[name]['image'] = get_image(name)

        save_products()
        save_price(name, products[name]["price"])
        check_and_save_new_emails()

        # Reset dei filtri al seguito dell'aggiunta del prodotto
        reset_filters()

        # Sblocco della Root al termine dell'aggiunta del prodotto
        unlock_root()

        logger.info(f"Prodotto '{name}' aggiunto con successo")

        root.focus_force()  # Forza il focus sulla finestra principale
        add_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    # Inizializza i dati del nuovo prodotto
    emails_and_thresholds = {}
    timer_refresh = 1800
    notify = tk.BooleanVar(value=True)

    # Configurazione del dialogo per l'aggiunta del prodotto
    add_product_dialog = tk.Toplevel(root)
    add_product_dialog.title("Aggiungi Prodotto")
    add_product_dialog.resizable(False, False)
    add_product_dialog.transient(root)
    add_product_dialog.grab_set()
    
    container = ttk.Frame(add_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    #Nome Prodotto
    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    name_entry_var = tk.StringVar()
    name_entry_var.trace_add("write", update_suggestions) # Regola per eseguire una funzione quando il contenuto di un widget cambia

    name_entry = ttk.Entry(container, width=80, font=("Arial", 10), textvariable=name_entry_var, validate="key", validatecommand=limit_letters)
    name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # Lista suggerimenti
    listbox_frame = ttk.Frame(add_product_dialog)
    listbox_frame.place_forget()

    listbox_suggestions = tk.Listbox(listbox_frame, width=80)
    listbox_suggestions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox_suggestions.yview)
    scrollbar.pack(side="right", fill="y")
    listbox_suggestions.config(yscrollcommand=scrollbar.set)

    # URL prodotto
    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    url_text = tk.Text(text_frame, height=5, width=80, font=("Arial", 10))
    url_text.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    url_text.config(yscrollcommand=scrollbar.set)

    # Notifiche
    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    # Pulsanti
    ttk.Button(container, text="Avanzate", command=lambda: open_advanced_dialog(add_product_dialog)).grid(row=3, column=0, pady=10, sticky="w")
    ttk.Button(container, text="Aggiungi", command=lambda: add_product(name_entry.get().strip().lower(), url_text.get("1.0", "end-1c").strip()),).grid(row=3, column=1, pady=10, sticky="e")

    # Definizione eventi widget
    name_entry.bind("<Button-3>", lambda e: show_text_menu(e, name_entry))
    name_entry.bind("<FocusIn>", update_suggestions)

    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)

    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))

    add_product_dialog.bind("<Button-1>", hide_suggestions)

    center_window(add_product_dialog)


def show_product_details(event=None):
    """
    Apri una finestra di dialogo con i dettagli del prodotto selezionato nella TreeView
    """
    def open_url(event):
        webbrowser.open(url)

    def open_prices_graph_panel(name):
        """
        Apre una finestra con un grafico dei prezzi del prodotto
        """
        def create_prices_graph(name):
            """
            Creazione del grafico dei prezzi
            """
            if name not in prices:
                raise ValueError(f"Prodotto '{name}' non trovato in prices")
            
            # Creazione del DataFrame dai dati dei prezzi del prodotto
            df = pd.DataFrame(prices[name])
            df["date"] = pd.to_datetime(df["date"])
            prices_graph = go.Figure()

            # Regola per la visualizzazione dei dettagli al passaggio del mouse
            prices_graph.add_trace(go.Scatter(x=df["date"], y=df["price"], mode="lines+markers", name=name, hovertemplate="Date: %{x}<br>Price: %{y}<extra></extra>"))

            # Personalizzazione dei layout del grafico
            prices_graph.update_layout(title=f"Prezzi del Prodotto: {name}", xaxis_title="Data", yaxis_title="Prezzo", xaxis=dict(type="date"), hovermode="x")
            
            return prices_graph

        def on_close(event=None):
            """
            Gestisce la chiusura della finestra del grafico dei prezzi
            """
            # Sblocco della Root alla chiusura del grafico dei prezzi
            unlock_root()

            os.remove(temp_file_path)

            web_view.setParent(None)
            web_view.deleteLater()

            prices_graph_application.quit()

        global prices_graph_application    

        # Blocco della Root durante la generazione del grafico dei prezzi
        block_root()

        # Creazione del grafico dei prezzi
        try:
            prices_graph = create_prices_graph(name)
        except ValueError as e:
            logger.error("Errore: " + str(e))

            # Sblocco della Root alla chiusura del grafico dei prezzi
            unlock_root()

            return
        
        html_str = pio.to_html(prices_graph, full_html=True)

        # Creazione di un file temporaneo per visualizzare il grafico HTML
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
            temp_file.write(html_str.encode("utf-8"))
            temp_file.flush()
            temp_file_path = temp_file.name

        # Creazione dell'applicazione e della finestra per visualizzare il grafico dei prezzi
        if prices_graph_application is None:
            prices_graph_application = QApplication([]) # Necessario per la visualizzazione del grafico

        prices_graph_window = QMainWindow()
        prices_graph_window.setWindowTitle(f"Grafico Prezzi - {name}")
        prices_graph_window.setMinimumSize(800, 600)
        prices_graph_window.setWindowModality(2) # Imposta la finestra in modalità applicazione (blocco finestra Tkinter)
        prices_graph_window.closeEvent = on_close

        # Imposta il grafico dei prezzi in una QWebEngineView
        central_widget = QWidget()

        qVBoxLayout = QVBoxLayout(central_widget)
        prices_graph_window.setCentralWidget(central_widget)

        web_view = QWebEngineView()
        web_view.setUrl(QUrl.fromLocalFile(temp_file_path))

        qVBoxLayout.addWidget(web_view)

        # Visualizza la finestra del grafico dei prezzi
        prices_graph_window.show()
        prices_graph_application.exec_()

    def copy_to_clipboard(text, show_info=False):
        """
        Copia il testo fornito negli appunti
        """
        pyperclip.copy(text)

        if show_info:
            messagebox.showinfo("Copia negli appunti", "URL copiato negli appunti!")

    selected_products = products_tree.selection()

    if not selected_products:
        logger.warning("Nessun prodotto selezionato per visualizzare i dettagli")
        return
    
    if len(selected_products) > 1:
        logger.warning("Più di un prodotto selezionato per visualizzare i dettagli")
        return
    
    # Carica i dati del prodotto selezionato
    name = selected_products[0]
    url = products[name]["url"]
    truncated_url = (url[:45] + "...") if len(url) > 45 else url # Troncamento url per la visualizzazione
    current_price = products[name]["price"]

    # Calcola statistiche sui prezzi dello storico del prodotto
    historical_prices = prices.get(name, [])
    all_prices = [entry["price"] for entry in historical_prices if isinstance(entry["price"], (int, float))]
    average_price, price_minimum, price_maximum = calculate_statistics(all_prices, current_price)

    # Calcolo del suggerimento per l'utente basato sui prezzi dello storico del prodotto
    text_suggestion, color_suggestion = calculate_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)
    
    # Creazione della finestra di dialogo con i dettagli del prodotto
    details_dialog = tk.Toplevel(root)
    details_dialog.title(f"Dettagli del prodotto: {name}")
    details_dialog.minsize(500, 300)
    details_dialog.resizable(False, False)
    details_dialog.configure(padx=20, pady=10)
    details_dialog.transient(root)
    details_dialog.grab_set()

    # Top frame per nome del prodotto, pulsanti e URL
    top_frame = ttk.Frame(details_dialog)
    top_frame.pack(fill="x", pady=10)

    top_frame.grid_columnconfigure(0, weight=1)
    top_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(top_frame, text=name, font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")

    ttk.Button(top_frame, text="Visualizza Grafico", command=lambda: open_prices_graph_panel(name)).grid(row=0, column=1, sticky="e")

    url_label = ttk.Label(top_frame, text=truncated_url, font=("Arial", 10), foreground="blue", cursor="hand2")
    url_label.grid(row=1, column=0, sticky="w")

    ttk.Button(top_frame, text="Copia URL", command=lambda: copy_to_clipboard(url)).grid(row=1, column=1, sticky="e")

    # Creazione di un frame orizzontale per i prezzi e l'immagine
    content_frame = ttk.Frame(details_dialog)
    content_frame.pack(fill="both", expand=True, pady=10)

    # Definire proporzioni per le colonne
    content_frame.grid_columnconfigure(0, weight=3, uniform="content")
    content_frame.grid_columnconfigure(1, weight=2, uniform="content")

    # Parte sinistra: prezzi storici e statistiche
    prices_frame = ttk.Frame(content_frame)
    prices_frame.grid(row=0, column=0, sticky="nsew", padx=10)

    # Frame interno per centrare i prezzi
    centered_prices_frame = ttk.Frame(prices_frame)
    centered_prices_frame.pack(fill="both", expand=True)

    ttk.Label(centered_prices_frame, text=f"Prezzo Attuale: {current_price:.2f}€" if isinstance(current_price, (int, float)) else "Prezzo Attuale: -", font=("Arial", 14, "bold"), foreground=color_suggestion).grid(row=0, column=0, sticky="w", pady=(5, 10))

    ttk.Label(centered_prices_frame, text="Prezzo Medio:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
    ttk.Label(centered_prices_frame, text=f"{average_price:.2f}€" if isinstance(average_price, (int, float)) else "-", font=("Arial", 10)).grid(row=1, column=1, sticky="e", pady=5)

    ttk.Label(centered_prices_frame, text="Prezzo Minimo Storico:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=5)
    ttk.Label(centered_prices_frame, text=f"{price_minimum:.2f}€" if isinstance(price_minimum, (int, float)) else "-", font=("Arial", 10)).grid(row=2, column=1, sticky="e", pady=5)

    ttk.Label(centered_prices_frame, text="Prezzo Massimo Storico:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=5)
    ttk.Label(centered_prices_frame, text=f"{price_maximum:.2f}€" if isinstance(price_maximum, (int, float)) else "-", font=("Arial", 10)).grid(row=3, column=1, sticky="e", pady=5)

    # Parte destra: immagine del prodotto
    image_frame = ttk.Frame(content_frame)
    image_frame.grid(row=0, column=1, sticky="nsew", padx=10)

    # Carica e ridimensiona l'immagine del prodotto
    image_path = products[name]['image']
    if image_path:
        try:
            # Apri l'immagine
            original_image = Image.open(image_path)
            print(f"Immagine caricata correttamente: {image_path}")

            # Dimensione desiderata
            target_size = (150, 150)

            # Ridimensiona forzatamente l'immagine
            resized_image = original_image.resize(target_size, Image.LANCZOS)

            # Converti l'immagine per Tkinter
            tk_image = ImageTk.PhotoImage(resized_image)

            # Aggiungi l'immagine a un Label nel frame immagine
            image_label = ttk.Label(image_frame, image=tk_image)
            image_label.pack(anchor="center")

            # Mantieni il riferimento all'immagine per evitare che venga garbage collected
            image_label.image = tk_image

        except Exception as e:
            logger.error(f"Errore nel caricamento dell'immagine: {e}")
    else:
        logger.warning(f"Nessuna immagine trovata per {name}")

        no_image_label = ttk.Label(image_frame, text="Aggiorna l'immagine", font=("Arial", 10, "bold"), foreground="red", background="lightgray", anchor="center")
        no_image_label.pack(fill="both", expand=True)

    # Visualizzazione del consiglio sull'acquisto
    ttk.Label(details_dialog, text=text_suggestion, font=("Arial", 12, "bold"), foreground=color_suggestion).pack(pady=10)

    # Pulsante chiusura finestra
    ttk.Button(details_dialog, text="Chiudi", command=details_dialog.destroy).pack(pady=10)

    # Definizione eventi widget
    url_label.bind("<Button-1>", open_url)

    # Centra la finestra di dialogo
    center_window(details_dialog)


def open_edit_product_dialog():
    """
    Apre una finestra di dialogo per modificare un prodotto, con funzionalità avanzate per gestire notifiche via email e soglie
    """
    def edit_product(name, current_url, new_url):
        """
        Modifica i dettagli di un prodotto esistente
        """
        if not new_url:
            messagebox.showwarning("Attenzione", "Compila l'URL!")
            return False
        
        # Verifica che l'URL non venga ripetuto su più prodotti
        if current_url != new_url:
            for existing_name in products:
                if new_url == products[existing_name]["url"]:
                    messagebox.showwarning("Attenzione", "Questo prodotto è già in monitoraggio!\nCambia l'URL")
                    return False

        # Blocco della Root durante la modifica del prodotto
        block_root()

        # Ricerca prezzo aggiornato
        new_price = get_price(new_url)

        # Aggiorna le informazioni del prodotto
        if new_price is None:
            products[name]["price"] = "Aggiorna o verifica l'URL: - "

            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica l'URL")

            logger.warning(f"Sul prodotto {name} non è stato trovato il prezzo sulla pagina " + products[name]["url"])
        else:
            products[name]["price"] = new_price

            # Verifica se una delle sogle impostate è più alta del nuovo prezzo
            for threshold in emails_and_thresholds.values():
                if threshold > new_price:
                    continueToEditProduct = messagebox.askyesno(
                        "Conferma soglia",
                        "La soglia di notifica che hai inserito è più alta del prezzo attuale.\nInserire comunque il prodotto con questa specifica?" 
                        if len(emails_and_thresholds) > 1 
                        else "Una delle soglie di notifica che hai inserito è più alta del prezzo attuale.\nInserire comunque il prodotto con questa specifica?" 
                    )

                    # Verifica risposta
                    if not continueToEditProduct:
                        # Sblocco della Root al termine della modifica del prodotto
                        unlock_root()
                        # Consenti la modifica della soglia
                        open_advanced_dialog()
                        return
                    
                    # E' inutile controllare altro se non importa che una delle soglie sia più alta del prezzo corrente
                    break

        products[name]["url"] = new_url
        products[name]["notify"] = notify.get()
        products[name]["timer"] = time.time()
        products[name]["timer_refresh"] = timer_refresh
        products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        products[name]["emails_and_thresholds"] = emails_and_thresholds
        products[name]["image"] = get_image(name)

        save_products()
        save_price(name, products[name]["price"])
        check_and_save_new_emails()

        # Reset dei filtri al seguito della modifica del prodotto
        reset_filters()

        # Sblocco della Root al termine della modifica del prodotto
        unlock_root()

        logger.info(f"Prodotto '{name}' modificato con successo")

        root.focus_force()  # Forza il focus sulla finestra principale
        edit_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    selected_products = products_tree.selection()[0]

    selected_name = products_tree.item(selected_products)["values"][0]
    
    # Carica i dati del prodotto selezionato
    selected_url = products[selected_name]["url"]
    emails_and_thresholds = products[selected_name]["emails_and_thresholds"]
    timer_refresh = products[selected_name]["timer_refresh"]
    notify = tk.BooleanVar(value=products[selected_name]["notify"])

    # Configurazione del dialogo per la modifica del prodotto
    edit_product_dialog = tk.Toplevel(root)
    edit_product_dialog.title("Modifica Prodotto")
    edit_product_dialog.resizable(False, False)
    edit_product_dialog.transient(root)
    edit_product_dialog.grab_set()

    container = ttk.Frame(edit_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    # Nome prodotto
    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    text_widget = tk.Text(container, font=("Arial", 10), height=1, width=80, wrap="none", bd=0, bg="white")
    text_widget.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    text_widget.insert(tk.END, selected_name)
    text_widget.config(state=tk.DISABLED)

    # URL Prodotto
    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    url_text = tk.Text(text_frame, height=5, width=80, font=("Arial", 10))
    url_text.pack(side="left", fill="both", expand=True)
    url_text.insert("1.0", selected_url)

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    url_text.config(yscrollcommand=scrollbar.set)

    # Notifiche
    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    # Pulsanti
    ttk.Button(container, text="Avanzate", command=lambda: open_advanced_dialog(edit_product_dialog)).grid(row=3, column=0, pady=10, sticky="w")
    ttk.Button(container, text="Salva", command=lambda: edit_product(selected_name, selected_url, url_text.get("1.0", "end-1c").strip())).grid(row=3, column=1, pady=10, sticky="e")

    # Definizione eventi widget
    text_widget.bind("<Button-3>", lambda e: show_text_menu(e, text_widget, True))
    
    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))

    center_window(edit_product_dialog)


def remove_products():
    """
    Rimozione dei prodotti selezionati dalla lista
    """
    def stop_tracking(name):
        """
        Blocco del monitoraggio del prodotto fermando il relativo thread
        """
        if name in stop_events:
            stop_events[name].set() # Segnala al thread corrente di fermarsi

        if name in threads:
            threads[name].join(timeout=1) # Aspetta che il thread corrente termini
            del threads[name]

    global stop_events, threads, hovered_row_products_tree

    selected_products = products_tree.selection()

    if not selected_products:
        logger.warning("Seleziona un prodotto dalla lista per rimuoverlo")
        return
    
    num_selected = len(selected_products)

    # Finestra di conferma per la rimozione dei prodotti
    continueToRemoveProduct = messagebox.askyesno(
        "Conferma rimozione",
        f"Sei sicuro di voler rimuovere i {num_selected} prodotti selezionati?" 
        if num_selected > 1 
        else "Sei sicuro di voler rimuovere il prodotto selezionato?"
    )

    # Verifica risposta
    if continueToRemoveProduct:
        # Reset dei filtri prima della rimozione dei prodotti
        reset_filters()

        # Blocco della Root durante la rimozione dei prodotti
        block_root()

        # Ciclo sui prodotti selezionati per rimuoverli
        for name in selected_products:
            # Ferma il monitoraggio del prodotto
            stop_tracking(name)
            
            # Rimozione prodotto
            del products[name]

            hovered_row_products_tree = None

            save_products()

            logger.info(f"Prodotto '{name}' rimosso con successo")

        # Sblocco della Root al termine della rimozione dei prodotti
        unlock_root()


def open_progress_dialog(update_all_prices=None, update_all_images=None):
    """
    Apre una finestra di dialogo per la barra di caricamento durante l'aggiornamento dei prezzi
    oppure delle immagini dei prodotti
    """
    def update_prices_threaded(loading_dialog, update_all_prices=True):
        """
        Funzione del thread separato per gestire l'aggiornamento dei prezzi
        """
        def update_prices(loading_dialog, products_to_update):
            """
            Aggiornamento dei prezzi dei prodotti e generazione di un messaggio di reportistica
            """
            # Impostazione dei valori limite per la barra di progresso
            max_value = len(products_to_update)
            loading_dialog.progress_bar["maximum"] = max_value
            loading_dialog.progress_bar["value"] = 0

            updated_products = []

            # Ciclo sui prodotti selezionati per aggiornarne i prezzi
            for product_index, name in enumerate(products_to_update):
                # Ricerca prezzo aggiornato
                current_price = get_price(products[name]["url"])
                
                # Aggiornamento della barra di progresso
                loading_dialog.progress_bar["value"] = product_index + 1
                loading_dialog.progress_label.config(text=f"Aggiornamento prezzo di {product_index + 1}/{max_value}...")
                loading_dialog.update_idletasks()

                # Gestione del caso in cui il prezzo non può essere aggiornato passando al prossimo prodotto da aggiornare
                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    
                    products[name]["price"] = "aggiorna o verifica l'URL: - "
                    products[name]["timer"] = time.time()
                    products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    continue
                
                # Aggiornamento del prodotto
                products[name]["price"] = current_price
                products[name]["timer"] = time.time()
                products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Recupera l'ultimo prezzo memorizzato del prodotto
                previous_price = get_last_price(name)

                # Aggiunta dei prodotti aggiornati alla lista per il report finale e notifica di un eventuale ribasso
                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price))
                
                    # Notifica dei prodotti la cui opzione di avviso è abilitata
                    if products[name]["notify"]:
                        send_notification_and_email(name, previous_price, current_price)

                save_price(name, products[name]["price"])

            save_products()

            # Impostazione dei valori limite per la barra di progresso
            loading_dialog.progress_label.config(text=f"Invio di eventuali notifiche...")
            loading_dialog.update_idletasks()
            
            # Visualizzazione di un messaggio con i risultati dell'aggiornamento ed eventualmente invio delle notifiche
            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, previous_price, current_price in updated_products:
                    # Costruzione messaggio reportistica
                    if current_price < previous_price:
                        status_message += (f"{name}: Prezzo calato da {previous_price}€ a {current_price}€\n")
                    elif current_price > previous_price:
                        status_message += f"{name}: Prezzo aumentato da {previous_price}€ a {current_price}€\n"
                    else:
                        status_message += f"{name}: Prezzo invariato a {current_price}€\n"

                messagebox.showinfo("Aggiornamento", status_message)
                logger.info("I prodotti sono stati aggiornati")
            else:
                messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali nuovamente")
                logger.warning("Nessun prodotto è stato aggiornato")

        # Reset dei filtri al seguito dell'aggiornamento dei prezzi
        reset_filters()

        # Blocco della Root durante l'aggiornamento dei prezzi
        block_root()
        
        # Aggiornamento dei prezzi di tutti i prodotti o solo di quelli selezionati
        if update_all_prices:
            update_prices(loading_dialog, products)
        else:
            selected_products = products_tree.selection()

            if not selected_products:
                logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
                return
            
            update_prices(loading_dialog, selected_products)

        # Sblocco della Root al termine dell'aggiornamento dei prezzi
        unlock_root()

        root.focus_force()  # Forza il focus sulla finestra principale
        loading_dialog.destroy()

    def update_new_images_threaded(loading_dialog, update_all_images=True):
        def check_and_save_new_images(loading_dialog, products_to_update):
            max_value = len(products_to_update)
            loading_dialog.progress_bar["maximum"] = max_value
            loading_dialog.progress_bar["value"] = 0
            
            for product_index, name in enumerate(products_to_update):
                products[name]['image'] = get_image(name)

                # Aggiornamento della barra di progresso
                loading_dialog.progress_bar["value"] = product_index + 1
                loading_dialog.progress_label.config(text=f"Aggiornamento immagine di {product_index + 1}/{max_value}...")
                loading_dialog.update_idletasks()
            
            save_products()
        # Blocco della Root durante l'aggiornamento dei prezzi
        block_root()
        
        # Aggiornamento delle immagini dei prodotti
        if update_all_images:
            check_and_save_new_images(loading_dialog, products)
        else:
            selected_products = products_tree.selection()

            if not selected_products:
                logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
                return
            
            check_and_save_new_images(loading_dialog, selected_products)

        # Sblocco della Root al termine dell'aggiornamento dei prezzi
        unlock_root()

        loading_dialog.destroy()

    # Dialog per informazioni sul caricamento
    loading_dialog = tk.Toplevel(root)
    loading_dialog.overrideredirect(True)
    loading_dialog.resizable(False, False)
    
    # Etichetta avanzamento
    progress_label = tk.Label(loading_dialog, text="Inizio aggiornamento...")
    progress_label.pack(pady=(10,5), padx=10)
    loading_dialog.progress_label = progress_label

    # Barra di caricamento
    progress_bar = ttk.Progressbar(loading_dialog, orient="horizontal", length=250, mode="determinate")
    progress_bar.pack(pady=(0,10), padx=10)
    loading_dialog.progress_bar = progress_bar

    center_window(loading_dialog)

    # Esecuzione dell'aggiornamento dei prezzi in un thread separato (necessario per la corretta visualizzazione del dialog)
    if update_all_prices is not None:
        thread = threading.Thread(target=update_prices_threaded, args=(loading_dialog, update_all_prices))
        thread.start()
    elif update_all_images is not None:
        thread = threading.Thread(target=update_new_images_threaded, args=(loading_dialog, update_all_images))
        thread.start()

    loading_dialog.wait_window()


def update_products_to_view(*args):
    """
    Aggiorna la lista dei prodotti da visualizzare in base al testo inserito nella barra di ricerca
    """
    global products_to_view

    if search_entry.get() != placeholder_text:
        # Resetta i filtri mantenendo lo stato corrente della barra di ricerca
        reset_filters(reset_search_bar=False)

        search_text = search_entry.get().strip()

        # Filtra i prodotti, altrimenti mostra tutti i prodotti
        if search_text != "":
            products_to_view = {name: details for name, details in products.items() if search_text.lower() in name.lower()}
        else:
            products_to_view = products


def show_text_menu(event, widget, onlyRead=False):
    """
    Mostra un menu contestuale per gestire operazioni di copia, taglio e incolla
    Il menu cambia comportamento se il widget è solo in lettura (onlyRead=True)
    """
    def is_text_selected(widget):
        """
        Verifica se c'è del testo selezionato nel widget
        """
        try:
            if isinstance(widget, tk.Text):
                return widget.tag_ranges(tk.SEL) != ()
            elif isinstance(widget, ttk.Entry) or isinstance(widget, tk.Entry):
                return widget.selection_present()
        except tk.TclError:
            return False
        return False

    def is_clipboard_available():
        """
        Verifica se ci sono dati disponibili negli appunti (clipboard)
        """
        try:
            return bool(root.clipboard_get())
        except tk.TclError:
            return False

    def copy_text(widget):
        """
        Copia il testo selezionato nel widget
        """
        try:
            widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def cut_text(widget):
        """
        Taglia il testo selezionato nel widget
        """
        try:
            widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def paste_text(widget):
        """
        Incolla il testo dagli appunti nel widget
        """
        try:
            widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    if widget == search_entry and search_entry.get() == placeholder_text:
        search_entry.delete(0, tk.END)
        search_entry.config(fg='black')

    text_menu = tk.Menu(root, tearoff=0)

    # Abilitazione comandi specifici in base alla situazione
    if onlyRead:
        if is_text_selected(widget):
            text_menu.add_command(label="Copia", command=lambda: copy_text(widget))
        else:
            text_menu.add_command(label="Copia", state="disabled")

        text_menu.add_command(label="Taglia", state="disabled")
        text_menu.add_command(label="Incolla", state="disabled")
    else:
        if is_text_selected(widget):
            text_menu.add_command(label="Taglia", command=lambda: cut_text(widget))
            text_menu.add_command(label="Copia", command=lambda: copy_text(widget))
        else:
            text_menu.add_command(label="Taglia", state="disabled")
            text_menu.add_command(label="Copia", state="disabled")

        if is_clipboard_available():
            text_menu.add_command(label="Incolla", command=lambda: paste_text(widget))
        else:
            text_menu.add_command(label="Incolla", state="disabled")

    # Mostra il menu contestuale alla posizione del clic del mouse
    text_menu.tk_popup(event.x_root, event.y_root)


def sort_by_column(column_name):
    """
    Ordinamento dei prodotti visualizzati nella TreeView in base alla colonna selezionata
    """
    global products_to_view

    # Cambio del tipo di ordinamento (ascendente, discendente, nessuno) quando la colonna è la stessa ordinata precedentemente
    if sort_state["column"] == column_name:
        sort_state["order"] = (sort_state["order"] + 1) % 3
    else:
        sort_state["column"] = column_name
        sort_state["order"] = 1

    # Elenco dei prodotti da visualizzare come lista di tuple
    list_products_to_view = list(products_to_view.items())
    
    # Mappa delle funzioni di ordinamento per ciascuna colonna
    column_key_map = {
        "Nome": lambda item: item[0].lower(),
        "URL": lambda item: item[1]["url"].lower(),
        "Prezzo": lambda item: item[1]["price"] if isinstance(item[1]["price"], (int, float)) else float("inf"),
        "Notifica": lambda item: item[1]["notify"],
        "Timer": lambda item: (item[1]["timer"] + item[1]["timer_refresh"]) - time.time(),
        "Timer Aggiornamento [s]": lambda item: item[1]["timer_refresh"],
        "Data Inserimento": lambda item: item[1]["date_added"],
        "Data Ultima Modifica": lambda item: item[1]["date_edited"]
    }
    
    # Gestione dei vari stati di ordinamento
    if sort_state["order"] == 0:
        list_products_to_view.sort(key=column_key_map["Data Ultima Modifica"])
        sort_state["column"] = None
    elif sort_state["order"] == 1:
        list_products_to_view.sort(key=column_key_map[column_name])
    else:
        list_products_to_view.sort(key=column_key_map[column_name], reverse=True)

    # Aggiornamento dell'ordine dei prodotti da visualizzare
    products_to_view = {name: details for name, details in list_products_to_view}

    # Ripristino delle intestazioni delle colonne nella TreeView
    for column in columns:
        products_tree.heading(column, text=column, anchor="center")

    # Aggiunta dell'indicatore di ordinamento alla colonna selezionata
    if sort_state["order"] != 0:
        sort_indicator = "▲" if sort_state["order"] == 1 else "▼"
        products_tree.heading(column_name, text=f"{column_name} {sort_indicator}", anchor="center")


def select_all_products(event=None):
    """
    Seleziona tutti i prodotti con ctrl + a
    """
    global current_index

    products_tree.selection_set(products_tree.get_children())

    current_index = None


def update_tree_view_columns_width(event=None):
    """
    Aggiorna la larghezza delle colonne della TreeView al variare della dimensione della finestra
    """
    # Ottieni la larghezza della finestra root
    current_root_width = root.winfo_width()
    
    # Evita l'adattamento delle colonne in caso la Root divenga troppo piccola
    if current_root_width >= 1550:
        # Ottieni la larghezza disponibile a partire da quella della Root
        available_width = current_root_width * 0.95
        
        # Controlla che la larghezza sia maggiore di zero
        if available_width > 0:
            # Imposta la larghezza di ciascuna colonna basata sulla percentuale
            for i, col in enumerate(columns):
                col_width = int(available_width * column_width_percentages[i])  # Calcola la larghezza
                products_tree.column(col, width=col_width)


def click(event):
    """
    Selezione prodotto con il tasto sinistro del mouse e multiselezione con ctrl + tasto sinistro del mouse
    Deseleziona tutti i prodotti se si seleziona qualcosa di diverso dallo stesso nella TreeView
    oppure rimuovi il focus dalle entry se si seleziona qualcosa di diverso dalla stessa
    """
    global current_index, click_index

    products_in_tree_view = products_tree.get_children()
    selected_products = products_tree.selection()

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    identified_product_index = products_tree.identify_row(event.y)

    # Gestione selezione di un prodotto oppure del focus sulle entry
    if isinstance(event.widget, ttk.Treeview) and identified_product_index in products_in_tree_view: # Non rimuovere isinstance, altrimenti clicca prodotti anche al di fuori del tree
        # Variabile globale utile per le condizioni della funzione arrow_navigation_and_shift_arrow
        click_index = products_in_tree_view.index(identified_product_index)

        current_index = click_index
        
        # Multiselezione con il tasto ctrl premuto 
        if event.state & 0x0004:
            # Toggle del prodotto
            if products_in_tree_view[current_index] in selected_products:
                products_tree.selection_remove(products_in_tree_view[current_index])
            else:
                products_tree.selection_add(products_in_tree_view[current_index])
        else:
            products_tree.selection_remove(*selected_products)
            products_tree.selection_add(products_in_tree_view[current_index])
    else:
        products_tree.selection_remove(*selected_products)

        current_index = None

        if not isinstance(event.widget, tk.Entry) or event.widget is None:
            if search_entry.get().strip() == "":
                search_entry.delete(0, tk.END)
                search_entry.insert(0, placeholder_text)
                search_entry.config(fg='grey')
            root.focus_set()
        else:
            if search_entry.get() == placeholder_text:
                search_entry.delete(0, tk.END)
                search_entry.config(fg='black')
        

def double_click(event):
    """
    Visualizza dettagli prodotto quando si clicca due volte su un prodotto
    """
    products_in_tree_view = products_tree.get_children()

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    identified_product_index = products_tree.identify_row(event.y)

    # Seleziona o deseleziona un prodotto in base a se è stato cliccato o meno
    if identified_product_index in products_in_tree_view:
        show_product_details()


def shift_click(event):
    """
    Multiselezione con shift + tasto sinistro del mouse
    """
    global current_index

    products_tree.selection_remove(*products_tree.selection())

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    identified_product = products_tree.identify_row(event.y)

    if not identified_product:
        return
    
    # Partenza dal primo prodotto se nessun prodotto è stato selezionato 
    if current_index is None:
        current_index = 0

    products_in_tree_view = products_tree.get_children()
    identified_product_index = products_in_tree_view.index(identified_product)

    # Determina l'intervallo tra current_index e l'indice del prodotto cliccato
    start = min(current_index, identified_product_index)
    end = max(current_index, identified_product_index)

    # Seleziona tutti i prodotti tra start e end, inclusi entrambi
    for i in range(start, end + 1):
        products_tree.selection_add(products_in_tree_view[i])


def arrow_navigation_and_shift_arrow(event):
    """
    Navigazione tra i prodotti con le frecce su/giu e multiselezione con shift + freccie su/giu
    """
    global current_index, click_index

    products_in_tree_view = products_tree.get_children()

    if products_in_tree_view is None:
        return

    selected_products = products_tree.selection()

    if selected_products:
        sorted_selected_indexes = [products_tree.index(item) for item in selected_products]
        sorted_selected_indexes.sort()

        # Rimuovi la selezione qual'ora i prodotti selezionati non fossero consecutivi o il mouse clicca il primo/l'ultimo prodotto durante la selezione multipla
        for index in range(1, len(sorted_selected_indexes)):
            if (sorted_selected_indexes[index] != sorted_selected_indexes[index - 1] + 1 
                or current_index not in sorted_selected_indexes 
                or (current_index > min(sorted_selected_indexes) and current_index < max(sorted_selected_indexes))
                or click_index == 0 or click_index == len(products_in_tree_view) - 1):
                products_tree.selection_remove(selected_products)

                if current_index is None:
                    current_index = products_tree.index(selected_products[0])

                # Seleziona solo l'elemento di current index
                products_tree.selection_add(products_in_tree_view[current_index])
                selected_products = products_tree.selection()

                break

    click_index = None
    
    # Gestisce la navigazione con i tasti freccia
    if event.keysym == "Down":
        # Partenza dal primo prodotto se nessun prodotto è stato selezionato
        if current_index is None:
            current_index = 0
            products_tree.selection_remove(selected_products)
            products_tree.selection_add(products_in_tree_view[current_index])
            return

        # Limita la selezione all'ultimo prodotto
        if current_index == len(products_in_tree_view) - 1 or products_in_tree_view[current_index] not in selected_products:
            products_tree.selection_add(products_in_tree_view[current_index])
            return

        # Calcola il prossimo prodotto da navigare  
        next_index  = min(current_index + 1, len(products_in_tree_view) - 1)
    else:
        # Partenza dall'ultimo prodotto se nessun prodotto è stato selezionato
        if current_index is None:
            current_index = len(products_in_tree_view) - 1
            products_tree.selection_remove(selected_products)
            products_tree.selection_add(products_in_tree_view[current_index])
            return
        
        # Limita la selezione al primo prodotto
        if current_index == 0 or products_in_tree_view[current_index] not in selected_products:
            products_tree.selection_add(products_in_tree_view[current_index])
            return
        
        # Calcola il prossimo prodotto da navigare  
        next_index = max(current_index - 1, 0)


    # Multiselezione con il tasto shift premuto 
    if event.state & 0x0001:
        # Toggle del prodotto
        if products_in_tree_view[next_index] in selected_products:
            products_tree.selection_remove(products_in_tree_view[current_index])
        else:
            products_tree.selection_add(products_in_tree_view[next_index])
    else:
        products_tree.selection_remove(selected_products)
        products_tree.selection_add(products_in_tree_view[next_index])

    # Scrolla la TreeView per rendere visibile il prodotto navigato/selezionato
    products_tree.see(products_in_tree_view[next_index])

    current_index = next_index


def on_menu_open():
    """
    Aggiornamento dello stato delle opzioni in base al numero di prodotti selezionati
    """
    num_selected_products = len(products_tree.selection())

    if num_selected_products == 1:
        action_menu.entryconfig("Visualizza", state="normal")
        action_menu.entryconfig("Modifica prodotto", state="normal")
        action_menu.entryconfig("Rimuovi prodotto", state="normal")
        products_menu.entryconfig("Aggiorna selezionati", state="normal")
        images_menu.entryconfig("Aggiorna selezionate", state="normal")
    elif num_selected_products > 1:
        action_menu.entryconfig("Visualizza", state="normal")
        action_menu.entryconfig("Modifica prodotto", state="normal")
        action_menu.entryconfig("Rimuovi prodotto", state="normal")
        products_menu.entryconfig("Aggiorna selezionati", state="normal")
        images_menu.entryconfig("Aggiorna selezionate", state="normal")
    else:
        action_menu.entryconfig("Visualizza", state="disabled")
        action_menu.entryconfig("Modifica prodotto", state="disabled")
        action_menu.entryconfig("Rimuovi prodotto", state="disabled")
        products_menu.entryconfig("Aggiorna selezionati", state="disabled")
        images_menu.entryconfig("Aggiorna selezionate", state="disabled")


def show_tree_view_menu(event):
    """
    Mostra il menu contestuale dopo il click del tasto destro del mouse
    Deseleziona tutti i prodotti se si seleziona qualcosa di diverso da un prodotto nella TreeView
    """
    global current_index

    products_in_tree_view = products_tree.get_children()
    selected_products = products_tree.selection()

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    identified_product_index = products_tree.identify_row(event.y)
    
    if identified_product_index in products_in_tree_view:
        # Selezione del prodotto, qual'ora questo non lo fosse
        if identified_product_index not in selected_products:
            products_tree.selection_set(identified_product_index)
            products_tree.focus(identified_product_index)

        selected_products = products_tree.selection()
    
        # Mostra il menu contestuale appropriato in base al numero di prodotti selezionati
        if len(selected_products) == 1:
            single_selection_menu.post(event.x_root, event.y_root)
        elif len(selected_products) > 1:
            multi_selection_menu.post(event.x_root, event.y_root)
    else:
        # Deseleziona solo se l'evento proviene dal widget della TreeView
        if event.widget == products_tree:
            products_tree.selection_remove(*selected_products)

            no_selection_menu.post(event.x_root, event.y_root)

            current_index = None


def on_hover_products_tree(event):
    """
    Evidenzia i prodotti sul TreeView al passaggio del mouse
    """
    global hovered_row_products_tree

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    row_id = products_tree.identify_row(event.y)

    # Se il mouse è sopra una riga e non è la stessa già evidenziata
    if row_id and row_id != hovered_row_products_tree:
        # Resetta il colore della riga precedentemente evidenziata
        if hovered_row_products_tree:
            products_tree.item(hovered_row_products_tree, tags=())

        # Assegna il tag "hover" alla nuova riga
        products_tree.item(row_id, tags=("hover",))

        hovered_row_products_tree = row_id

    # Se il mouse non è sopra una riga, resetta l'hover
    elif not row_id and hovered_row_products_tree:
        if hovered_row_products_tree in products_to_view:
            products_tree.item(hovered_row_products_tree, tags=())
        hovered_row_products_tree = None


def periodic_refresh_root():
    """
    Aggiornamento periodico della Root
    """
    def refresh_tree_view():
        """
        Aggiornamento della TreeView con i prodotti monitorati
        """
        def calculate_remaining_time(last_checked_time, update_interval):
            """
            Calcolo tempo rimanente fino al prossimo aggiornamento
            """
            next_check = last_checked_time + update_interval
            remaining_time = next_check - time.time()
            
            # Il tempo rimanente non può mai essere inferiore a 0
            if remaining_time < 0:
                remaining_time = 0

            hours, remainder = divmod(remaining_time, 3600)
            minutes, seconds = divmod(remainder, 60)

            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        products_in_tree_view = products_tree.get_children()
        
        # Non spostarlo da qui perchè il reset della TreeView mi fa perdere le selezioni
        selected_products = products_tree.selection()

        # Reset della TreeView
        products_tree.delete(*products_in_tree_view)

        # Inserimento dei prodotti con i dati aggiornati nella TreeView
        for name in products_to_view:
            products_tree.insert("", "end", iid=name, 
                                 values=(name,products_to_view[name]["url"], 
                                         f"{str(products_to_view[name]['price'])}€",
                                        "Si" if products_to_view[name]["notify"] else "No",
                                        calculate_remaining_time(products_to_view[name]["timer"], products_to_view[name]["timer_refresh"]),
                                        products_to_view[name]["timer_refresh"],
                                        products_to_view[name]["date_added"],
                                        products_to_view[name]["date_edited"]
                                        ))
        
        products_in_tree_view = products_tree.get_children()

        # Ripristino della selezione precedentemente salvata nella TreeView
        for product in selected_products:
            if product in products_in_tree_view:
                products_tree.selection_add(product)

        # Ripristina la riga in hover, se esiste ancora
        if hovered_row_products_tree in products_in_tree_view:
            products_tree.item(hovered_row_products_tree, tags=("hover",))

    if is_possible_to_refresh_root:
        refresh_tree_view()

        # Chiama ricorsivamente la funzione dopo 500 millisecondi per creare un aggiornamento periodico della Root
        root.after(500, periodic_refresh_root)


def set_periodic_refresh_root(update=True):
    """
    Funzione principale che gestisce l'abilitazione o la disabilitazione del refresh periodico
    Se `update` è True, abilita i controlli, resettando i thread che monitorano i prodotti e avviando il refresh periodico
    Se `update` è False, disabilita i controlli e ferma i thread che monitorano i prodotti
    """
    def reset_threads():
        """
        Reset dei thread che monitorano i prodotti
        """
        for name in products:
            start_tracking(name, products[name]["url"])

    def stop_threads():
        """
        Ferma i thread che monitorano i prodotti
        """
        for name in products:
            stop_events[name].set() # Segnala al thread corrente di fermarsi
            threads[name].join(timeout=1) # Aspetta che il thread corrente termini
            del threads[name]

    global is_possible_to_refresh_root

    if update:
        is_possible_to_refresh_root = True
        periodic_refresh_root()
        reset_threads()
    else:
        is_possible_to_refresh_root = False
        stop_threads()


# Variabili globali
columns = ("Nome", "URL", "Prezzo", "Notifica", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica")
column_width_percentages = [0.210, 0.175, 0.135, 0.055, 0.075, 0.12, 0.115, 0.115]

config_file = "config.json"

products_file = "products.json"
products = {}
products_to_view = {}

prices_file = "prices.json"
prices = {}
prices_graph_application = None

emails_file = "emails.json"
emails = []

images_dir = os.path.join(os.getcwd(), "images")

threads = {}
stop_events = {}

sort_state = {
    "column": None,
    "order": 0,  # 0: nessun ordinamento, 1: crescente, 2: decrescente
}

current_index = None

click_index = None

is_possible_to_refresh_root = True

hovered_row_products_tree = None
hovered_row_email_and_threshold_tree = None

# Interfaccia principale
root = tk.Tk()
root.title("Monitoraggio Prezzi Amazon")
root.minsize(900, 300)
root.wm_state("zoomed")

limit_letters = (root.register(lambda s: len(s) <= 50), "%P") # Regola per limitare i caratteri da inserire

# Creazione della barra di menu
menu_bar = tk.Menu(root)
menu_bar.configure(postcommand=on_menu_open)

# Menu "File"
file_menu = tk.Menu(menu_bar, tearoff=0)
file_menu.add_command(label="Nuovo", command=open_add_product_dialog)
file_menu.add_separator()
file_menu.add_command(label="Esci", command=root.quit)


# Menu "Modifica"
action_menu = tk.Menu(menu_bar, tearoff=0)
action_menu.add_command(label="Visualizza", command=show_product_details, state="disabled")
action_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog, state="disabled")
action_menu.add_command(label="Rimuovi prodotto", command=remove_products, state="disabled")

# Menu "Aggiorna"
update_menu = tk.Menu(menu_bar, tearoff=0)

images_menu = tk.Menu(update_menu, tearoff=0)
images_menu.add_command(label="Aggiorna immagini", command=lambda: open_progress_dialog(update_all_images=True))
images_menu.add_command(label="Aggiorna selezionate", command=lambda: open_progress_dialog(update_all_images=False), state="disabled")
images_menu.add_command(label="Vai alla cartella immagini", command=open_images_folder)
update_menu.add_cascade(label="Immagini", menu=images_menu)

products_menu = tk.Menu(update_menu, tearoff=0)
products_menu.add_command(label="Aggiorna prodotti", command=lambda: open_progress_dialog(update_all_prices=True))
products_menu.add_command(label="Aggiorna selezionati", command=lambda: open_progress_dialog(update_all_prices=False), state="disabled")
update_menu.add_cascade(label="Prodotti", menu=products_menu)

# Menu "Impostazioni"
history_menu = tk.Menu(menu_bar, tearoff=0)
history_menu.add_command(label="Pulisci cronologia prodotti", command=clean_products_and_prices_history)
history_menu.add_command(label="Pulisci cronologia email", command=clean_emails_history)

# Menu "Aiuto"
help_menu = tk.Menu(menu_bar, tearoff=0)
help_menu.add_command(label="Info", command=open_about_dialog)

# Aggiungi il menu "Modifica" alla barra di menu
menu_bar.add_cascade(label="File", menu=file_menu)
menu_bar.add_cascade(label="Azioni", menu=action_menu)
menu_bar.add_cascade(label="Aggiorna", menu=update_menu)
menu_bar.add_cascade(label="Impostazioni", menu=history_menu)
menu_bar.add_cascade(label="Aiuto", menu=help_menu)

# Configura la barra di menu nell'interfaccia principale
root.config(menu=menu_bar)

# Barra di ricerca
placeholder_text = "Cerca un prodotto..."

# Crea una StringVar per monitorare le modifiche all'Entry
search_entry_var = tk.StringVar()
search_entry_var.trace_add("write", update_products_to_view)

search_entry = tk.Entry(root, width=75, font=("Arial", 12), validate="key", validatecommand=limit_letters, textvariable=search_entry_var)
search_entry.pack(padx=40, pady=20, anchor= "e")

# Imposta il placeholder
search_entry.insert(0, placeholder_text)
search_entry.config(fg='grey')  # Colore del testo del placeholder

# Configura lo stile della Treeview
style = ttk.Style()
style.configure("Treeview", rowheight=25)

# Lista prodotti
frame_products_list = ttk.Frame(root)
frame_products_list.pack(fill="both", expand=True, padx=(15, 10), pady=(10, 0))

products_tree = ttk.Treeview(frame_products_list, columns=columns, show="headings", selectmode="none")
products_tree.grid(row=0, column=0, sticky="nsew")

for col in columns:
    products_tree.heading(col, text=col, anchor="center", command=lambda _col=col: sort_by_column(_col))
    products_tree.column(col,
                         anchor="center" if col in ["Prezzo", "Notifica", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica"] else "w", 
                         stretch=False)
    
scrollbar_vertical = ttk.Scrollbar(frame_products_list, orient="vertical", command=products_tree.yview)
scrollbar_vertical.grid(row=0, column=1, sticky="ns")

scrollbar_horizontal = ttk.Scrollbar(frame_products_list, orient="horizontal", command=products_tree.xview)
scrollbar_horizontal.grid(row=1, column=0, sticky="ew")

frame_products_list.grid_rowconfigure(0, weight=1)
frame_products_list.grid_columnconfigure(0, weight=1)

products_tree.configure(yscrollcommand=scrollbar_vertical.set, xscrollcommand=scrollbar_horizontal.set)
products_tree.tag_configure("hover", background="#cceeff")

# Footer
frame_footer = ttk.Frame(root)
frame_footer.pack(side="bottom", fill="x", padx=(20, 40), pady=2)

creator_label = tk.Label(frame_footer, text="Prodotto da Vincenzo Salvati", font=("Arial", 8))
creator_label.pack(side="right")

# Menu tasto destro
single_selection_menu = tk.Menu(root, tearoff=0)
single_selection_menu.add_command(label="Visualizza prodotto", command=show_product_details)
single_selection_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog)
single_selection_menu.add_command(label="Rimuovi prodotto", command=remove_products)
single_selection_menu.add_command(label="Aggiorna selezionato", command=lambda: open_progress_dialog(update_all_prices=False))

multi_selection_menu = tk.Menu(root, tearoff=0)
multi_selection_menu.add_command(label="Rimuovi selezionati", command=remove_products)
multi_selection_menu.add_command(label="Aggiorna selezionati", command=lambda: open_progress_dialog(update_all_prices=False))

no_selection_menu = tk.Menu(root, tearoff=0)
no_selection_menu.add_command(label="Nuovo", command=open_add_product_dialog)

# Definizione eventi root e product_tree
root.bind("<Control-a>", select_all_products)
root.bind("<Configure>", update_tree_view_columns_width)
root.bind("<Button-1>", click)
root.bind("<Shift-Button-1>", shift_click)
root.bind("<Down>", arrow_navigation_and_shift_arrow)
root.bind("<Up>", arrow_navigation_and_shift_arrow)

search_entry.bind("<Button-3>", lambda e: show_text_menu(e, search_entry))

products_tree.bind("<Double-1>", double_click)
products_tree.bind("<Return>", show_product_details)
products_tree.bind("<Button-3>", show_tree_view_menu)
products_tree.bind("<Motion>", on_hover_products_tree)

# Carica i dati
load_products()
load_prices()
load_emails()

check_and_save_new_emails()

# Avvio interfaccia
root.after(150, update_tree_view_columns_width)
periodic_refresh_root()
root.mainloop()
