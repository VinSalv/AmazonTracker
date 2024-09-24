import logging
import re
import statistics
import webbrowser
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
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
logger_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(logger_handler)


def load_products_data():
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
            with open(prices_file, "w") as file:
                json.dump({}, file)
            
                logger.warning(f"File dei dati prodotti '{products_file}' non trovato, creato nuovo file vuoto")
                messagebox.showwarning("Attenzione", f"File dei dati prodotti '{products_file}' non trovato\nCreato nuovo file vuoto")
        except Exception as e:
            logger.error(f"Errore durante la creazione del file dei dati prodotti: {e}")
            messagebox.showerror("Attenzione", "Errore durante la creazione del file dei dati prodotti")
            exit()


def save_products_data():
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


def load_prices_data():
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


def save_prices_data(name, price):
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
    
    def send_email(subject, body, email_to_notify):
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
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP("smtp.gmail.com", 587) # Imposta connessione al server SMTP
            server.starttls() # Abilita connessionE TLS
            server.login(from_email, from_password)
            server.sendmail(from_email, email_to_notify, msg.as_string())
            server.quit()
        except Exception as e:
            logger.error(f"Impossibile inviare l'email: {e}")

    def send_default_notification(subject, body):
        """
        Invia una email e una notifica Telegram al desinatario di default
        """
        # Carica i contatti del destinatario di default
        _, _, default_recipient_email, default_url_telegram, default_chat_id_telegram = load_config()

        # Invia email
        send_email(subject, body, default_recipient_email)

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
    body = (
        f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n"
        + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
        + f"Acquista ora: {products[name]['url']}"
    )
    
    # Invio notifica telegram
    if current_price-1 < previous_price:
        send_default_notification(subject=subject, body=body)

    # Controllo delle soglie e invio delle e-mail
    for email, threshold in products[name]["emails_and_thresholds"].items():
        value_to_compare = previous_price
        subject_to_send = subject
        body_to_send = body

        # Tenere conto della soglia nel caso in cui fosse settata
        if threshold != 0.0:
            value_to_compare = threshold
            subject_to_send = "Prezzo inferiore alla soglia indicata!"
            body_to_send = (
                f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.\n"
                + f"Il costo attuale è {current_price}€.\n\n"
                + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
                + f"Acquista ora: {products[name]['url']}"
            )

        # Invio e-mail in caso di diminuizione del prezzo o diminuizione oltre la soglia
        if current_price-1 < value_to_compare:
            send_email(subject=subject_to_send, body=body_to_send, email_to_notify=email)


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

            save_prices_data(name, products[name]["price"])
            save_products_data()

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


def open_advanced_dialog():
    """
    Apre il dialogo avanzato per aggiungere soglie di notifica via email
    """
    def add_email_threshold():
        """
        Aggiunta di email e soglia di prezzo
        """
        email = email_entry.get().strip()
        threshold = threshold_entry.get().strip()

        if not email:
            messagebox.showwarning("Attenzione", "Compila l'email!")
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
        update_email_and_threshold_table()

        # Svuota i campi
        email_entry.delete(0, "end")
        threshold_entry.delete(0, "end")

    def update_email_and_threshold_table():
        """
        Aggiorna la tabella che mostra le e-mail e le soglie
        """
        # Svuota tabella delle e-mail e dei threshold
        email_and_threshold_table.delete(*email_and_threshold_table.get_children())

        # Riempi la tabella delle e-mail e dei threshold con i valori aggiornati
        for key, value in sorted(emails_and_thresholds.items()):
            email_and_threshold_table.insert("", "end", iid=key, values=(key, str(value) + "€" if value != 0.0 else "Nessuna soglia definita"))

    def show_email_and_threshold_menu(event):
        """
        Mostra un menu contestuale per modificare una soglia o rimuovere un'e-mail
        """
        # Identifica l'e-mail cliccata (basato sulla posizione y del click)
        identified_email = email_and_threshold_table.identify_row(event.y)

        if not identified_email:
            return
        
        # Selezione dell'e-mail cliccata
        email_and_threshold_table.selection_set(identified_email)

        # Mostra menu contestuale
        email_threshold_menu.post(event.x_root, event.y_root)

    def remove_email():
        """
        Rimuove l'email selezionata dalla tabella
        """
        email = email_and_threshold_table.selection()[0]

        del emails_and_thresholds[email]
        
        # Aggiornamento della tabella dopo la rimozione
        update_email_and_threshold_table()

    def modify_threshold():
        """
        Modifica la soglia di notifica per l'email selezionata
        """
        email = email_and_threshold_table.selection()[0]

        # Inserimento della nuova soglia
        new_threshold = simpledialog.askstring("Modifica Soglia", f"Soglia di notifica per '{email}':")
        new_threshold = new_threshold.replace(" ", "")

        if new_threshold == "":
            new_threshold = 0.0

        try:
            emails_and_thresholds[email] = float(new_threshold)

            # Aggiornamento della tabella dopo la modifica
            update_email_and_threshold_table()
        except:
            messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")

    def validate_timer_input(input_value):
        """
        Validazione dell'input del timer, accettando solo numeri positivi o stringhe vuote
        """
        return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

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

    advanced_dialog = tk.Toplevel(root)
    advanced_dialog.title("Aggiungi e-mail e soglia notifica")
    advanced_dialog.resizable(False, False)
    advanced_dialog.transient(root)
    advanced_dialog.grab_set()
    
    container = ttk.Frame(advanced_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    # E-mail
    ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    email_entry = ttk.Entry(container, width=40, font=common_font)
    email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # Soglia
    ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    threshold_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(lambda s: s.isdigit() or s in [".", "-"]), "%S"))
    threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")

    # Pulsante
    add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
    add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

    # Lista delle e-mail e delle soglie
    email_and_threshold_table = ttk.Treeview(container, columns=("Email", "Soglia"), show="headings")
    email_and_threshold_table.grid(row=3, column=0, columnspan=2, pady=10, sticky="nsew")
    email_and_threshold_table.heading("Email", text="Email")
    email_and_threshold_table.heading("Soglia", text="Soglia")
    email_and_threshold_table.column("Email", width=200)
    email_and_threshold_table.column("Soglia", width=120, anchor="center")
    vsb = ttk.Scrollbar(container, orient="vertical", command=email_and_threshold_table.yview)
    vsb.grid(row=3, column=2, sticky="ns")
    email_and_threshold_table.configure(yscrollcommand=vsb.set)

    # Timer aggiornamento
    ttk.Label(container, text="Timer [s]:").grid(row=4, column=0, padx=10, pady=10, sticky="we")
    
    timer_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(validate_timer_input), "%P"))
    timer_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")
    timer_entry.insert(0, timer_refresh)

    # Menu tasto destro        
    email_threshold_menu = tk.Menu(advanced_dialog, tearoff=0)
    email_threshold_menu.add_command(label="Modifica Soglia", command=modify_threshold)
    email_threshold_menu.add_command(label="Rimuovi Email", command=remove_email)

    # Definizione eventi widget
    email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))

    threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

    email_and_threshold_table.bind("<Button-3>", show_email_and_threshold_menu)

    timer_entry.bind("<KeyRelease>", on_timer_change)
    timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))
    
    # Mostra eventuali e-mail e relative soglie nella tabella
    update_email_and_threshold_table()

    center_window(advanced_dialog)


def open_add_product_dialog():
    """
    Apre una finestra di dialogo per aggiungere un prodotto, con funzionalità avanzate per gestire notifiche via email e soglie
    """
    def hide_suggestions(event=None):
        """
        Nasconde il frame che contiene la `listbox_suggestions`
        """
        listbox_frame.place_forget()

    def update_suggestions(*args):
        """
        Aggiorna i suggerimenti nella `listbox_suggestions` in base al testo inserito in `name_entry`
        """
        typed_text = name_entry_var.get().strip().lower()

        # Reset della lista di suggerimenti
        listbox_suggestions.delete(0, tk.END)

        if typed_text:
            # Ricerca dei nomi dei prodotti che contengono il testo digitato
            matching_suggestions = [name for name in prices.keys() if typed_text in name.lower()]

            # Aggiunta del testo corrente alla lista dei suggerimenti qual'ora non fosse già presente
            if name_entry.get() not in matching_suggestions:
                listbox_suggestions.insert(tk.END, name_entry.get())

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

            listbox_frame.place_forget()

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
        
        # Ricerca prezzo
        current_price = get_price(url)

        if current_price is None:
            current_price = "Aggiorna o verifica url: - "
            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica url")

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
        }

        save_products_data()
        save_prices_data(name, products[name]["price"])

        # Avvia il monitoraggio del prodotto
        start_tracking(name, url)

        # Reset dei filtri al seguito dell'aggiunta del prodotto
        reset_filters()

        logger.info(f"Prodotto '{name}' aggiunto con successo")

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

    name_entry = ttk.Entry(container, width=80, font=common_font, textvariable=name_entry_var, validate="key", validatecommand=limit_letters)
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

    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    url_text.config(yscrollcommand=scrollbar.set)

    # Notifiche
    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    # Pulsanti
    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")
    ttk.Button(container, text="Aggiungi", command=lambda: add_product(name_entry.get().strip().lower(), url_text.get("1.0", "end-1c").strip()),).grid(row=3, column=1, pady=10, sticky="e")

    # Definizione eventi widget
    name_entry.bind("<Button-3>", lambda e: show_text_menu(e, name_entry))
    name_entry.bind("<FocusIn>", update_suggestions)
    name_entry.bind("<FocusOut>", hide_suggestions)

    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)

    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))

    center_window(add_product_dialog)


def show_product_details(event=None):
    """
    Apri una finestra di dialogo con i dettagli del prodotto selezionato nella TreeView
    """
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

        def disable_tkinter_windows(root):
            """
            Disabilita tutte le finestre Tkinter aperte, compresa la finestra principale.
            """
            for window in root.winfo_children():
                try:
                    window.attributes("-disabled", True)
                except:
                    pass

            root.attributes("-disabled", True)

        def enable_tkinter_windows(root):
            """
            Abilita tutte le finestre Tkinter aperte, compresa la finestra principale.
            """
            for window in root.winfo_children():
                try:
                    window.attributes("-disabled", False)
                except:
                    pass

            root.attributes("-disabled", False)

        def on_close(event=None):
            """
            Gestisce la chiusura della finestra del grafico dei prezzi
            """
            set_periodic_refresh_root()
            
            enable_tkinter_windows(root)

            os.remove(temp_file_path)

            web_view.setParent(None)
            web_view.deleteLater()

            prices_graph_application.quit()

        global prices_graph_application

        set_periodic_refresh_root(False)

        disable_tkinter_windows(root)

        # Creazione del grafico dei prezzi
        try:
            prices_graph = create_prices_graph(name)
        except ValueError as e:
            logger.error("Errore: " + str(e))

            set_periodic_refresh_root()

            enable_tkinter_windows(root)
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
    details_window = tk.Toplevel(root)
    details_window.title(f"Dettagli del prodotto: {name}")
    details_window.minsize(500, 300)
    details_window.resizable(False, False)
    details_window.configure(padx=20, pady=10)
    details_window.transient(root)
    details_window.grab_set()

    # Visualizzazione dei dettagli del prodotto
    name_font = ("Helvetica", 12, "bold")
    highlight_font = ("Helvetica", 14, "bold")

    top_frame = ttk.Frame(details_window)
    top_frame.pack(fill="x", pady=10)
    
    top_frame.grid_columnconfigure(0, weight=1)
    top_frame.grid_columnconfigure(1, weight=1)
    top_frame.grid_columnconfigure(2, weight=0)

    ttk.Label(top_frame, text=name, font=name_font).grid(row=0, column=0, sticky="w")

    ttk.Button(top_frame, text="Visualizza Grafico", command=lambda: open_prices_graph_panel(name)).grid(row=0, column=1, sticky="e")

    url_label = ttk.Label(top_frame, text=truncated_url, font=common_font, foreground="blue", cursor="hand2")
    url_label.grid(row=1, column=0, sticky="w")

    ttk.Button(top_frame, text="Copia URL", command=lambda: copy_to_clipboard(url)).grid(row=1, column=1, sticky="e")

    # Visualizzazione dei prezzi storici e delle statistiche
    prices_frame = ttk.Frame(details_window)
    prices_frame.pack(anchor="w", padx=10)

    ttk.Label(prices_frame, text=f"Prezzo Attuale: {current_price:.2f}€" if isinstance(current_price, (int, float)) else "Prezzo Attuale: -", font=highlight_font, foreground=color_suggestion).grid(row=0, column=0, sticky="w", pady=(5, 10))
    
    ttk.Label(prices_frame, text="Prezzo Medio:", font=common_font).grid(row=1, column=0, sticky="w", pady=5)
    ttk.Label(prices_frame, text=f"{average_price:.2f}€" if isinstance(average_price, (int, float)) else "-", font=common_font).grid(row=1, column=1, sticky="e", pady=5)

    ttk.Label(prices_frame, text="Prezzo Minimo Storico:", font=common_font).grid(row=2, column=0, sticky="w", pady=5)
    ttk.Label(prices_frame, text=f"{price_minimum:.2f}€" if isinstance(price_minimum, (int, float)) else "-", font=common_font).grid(row=2, column=1, sticky="e", pady=5)

    ttk.Label(prices_frame, text="Prezzo Massimo Storico:", font=common_font).grid(row=3, column=0, sticky="w", pady=5)
    ttk.Label(prices_frame, text=f"{price_maximum:.2f}€" if isinstance(price_maximum, (int, float)) else "-", font=common_font).grid(row=3, column=1, sticky="e", pady=5)
    
    # Visualizzazione del cosniglio sull'acquisto
    ttk.Label(details_window, text=text_suggestion, font=name_font, foreground=color_suggestion).pack(pady=10)

    # Pulsante chiusura finestra
    ttk.Button(details_window, text="Chiudi", command=details_window.destroy).pack(pady=10)

    # Definizione eventi widget
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    center_window(details_window)


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

        # Ricerca prezzo aggiornato
        new_price = get_price(new_url)

        # Aggiorna le informazioni del prodotto
        if new_price is None:
            products[name]["price"] = "Aggiorna o verifica l'URL: - "

            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica l'URL")

            logger.warning(f"Sul prodotto {name} non è stato trovato il prezzo sulla pagina " + products[name]["url"])
        else:
            products[name]["price"] = new_price

        products[name]["url"] = new_url
        products[name]["notify"] = notify.get()
        products[name]["timer"] = time.time()
        products[name]["timer_refresh"] = timer_refresh
        products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        products[name]["emails_and_thresholds"] = emails_and_thresholds

        save_products_data()
        save_prices_data(name, products[name]["price"])

        # Riavvia il monitoraggio del prodotto
        start_tracking(name, new_url)

        # Reset dei filtri al seguito della modifica del prodotto
        reset_filters()

        logger.info(f"Prodotto '{name}' modificato con successo")

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

    text_widget = tk.Text(container, font=common_font, height=1, width=80, wrap="none", bd=0, bg="white")
    text_widget.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    text_widget.insert(tk.END, selected_name)
    text_widget.config(state=tk.DISABLED)

    # URL Prodotto
    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
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
    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")
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

    global stop_events, threads

    selected_products = products_tree.selection()

    if not selected_products:
        logger.warning("Seleziona un prodotto dalla lista per rimuoverlo")
        return
    
    num_selected = len(selected_products)

    # Finestra di conferma per la rimozione dei prodotti
    response = messagebox.askyesno(
        "Conferma rimozione",
        f"Sei sicuro di voler rimuovere i {num_selected} prodotti selezionati?" 
        if num_selected > 1 
        else "Sei sicuro di voler rimuovere il prodotto selezionato?"
    )

    # Verifica risposta
    if response:
        # Reset dei filtri prima della rimozione dei prodotti
        reset_filters()

        # Ciclo sui prodotti selezionati per rimuoverli
        for name in selected_products:
            # Ferma il monitoraggio del prodotto
            stop_tracking(name)
            
            # Rimozione prodotto
            del products[name]

            save_products_data()

            logger.info(f"Prodotto '{name}' rimosso con successo")


def open_progress_dialog(update_all=True):
    """
    Apre una finestra di dialogo per la barra di caricamento durante l'aggiornamento dei prezzi dei prodotti
    Il processo di aggiornamento può essere applicato a tutti i prodotti o solo a quelli selezionati, a seconda
    del parametro `update_all`
    """
    def update_prices_threaded(dialog, update_all=True):
        """
        Funzione del thread separato per gestire l'aggiornamento dei prezzi
        """
        def update_prices(dialog, products_to_update):
            """
            Aggiornamento dei prezzi dei prodotti e generazione di un messaggio di reportistica
            """
            # Impostazione dei valori limite per la barra di progresso
            max_value = len(products_to_update)
            dialog.progress_bar["maximum"] = max_value
            dialog.progress_bar["value"] = 0

            updated_products = []

            # Ciclo sui prodotti selezionati per aggiornarne i prezzi
            for product_index, name in enumerate(products_to_update):
                # Ricerca prezzo aggiornato
                current_price = get_price(products[name]["url"])
                
                # Aggiornamento della barra di progresso
                dialog.progress_bar["value"] = product_index + 1
                dialog.progress_label.config(text=f"Aggiornamento di {product_index + 1}/{max_value}...")
                dialog.update_idletasks()

                # Gestione del caso in cui il prezzo non può essere aggiornato passando al prossimo prodotto da aggiornare
                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    
                    products[name]["price"] = "Aggiorna o verifica url: - "
                    products[name]["timer"] = time.time()
                    products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    continue
                
                # Aggiornamento del prodotto
                products[name]["price"] = current_price
                products[name]["timer"] = time.time()
                products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Recupera l'ultimo prezzo memorizzato del prodotto
                previous_price = get_last_price(name)

                # Aggiunta dei prodotti aggiornati alla lista per il report finale
                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price))

                save_prices_data(name, products[name]["price"])

            save_products_data()

            # Impostazione dei valori limite per la barra di progresso
            dialog.progress_label.config(text=f"Invio di eventuali notifiche...")
            dialog.update_idletasks()
            
            # Visualizzazione di un messaggio con i risultati dell'aggiornamento ed eventualmente invio delle notifiche
            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, previous_price, current_price in updated_products:
                    # Notifica dei prodotti la cui opzione di avviso è abilitata
                    if products[name]["notify"]:
                        send_notification_and_email(name, previous_price, current_price)

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
        set_periodic_refresh_root(False)
        root.resizable(False, False)
        root.wm_attributes("-disabled", True)
        
        # Aggiornamento dei prezzi di tutti i prodotti o solo di quelli selezionati
        if update_all:
            update_prices(dialog, products)
        else:
            selected_products = products_tree.selection()

            if not selected_products:
                logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
                return
            
            update_prices(dialog, selected_products)

        # Sblocco della Root al termine dell'aggiornamento dei prezzi
        set_periodic_refresh_root()
        root.resizable(True, True)
        root.wm_attributes("-disabled", False)

        dialog.destroy()

    # Dialog per informazioni sul caricamento
    dialog = tk.Toplevel(root)
    dialog.grab_set()
    dialog.overrideredirect(True)
    dialog.resizable(False, False)
    
    # Etichetta avanzamento
    progress_label = tk.Label(dialog, text="Inizio aggiornamento...")
    progress_label.pack(pady=(10,5), padx=10)
    dialog.progress_label = progress_label

    # Barra di caricamento
    progress_bar = ttk.Progressbar(dialog, orient="horizontal", length=250, mode="determinate")
    progress_bar.pack(pady=(0,10), padx=10)
    dialog.progress_bar = progress_bar

    center_window(dialog)

    # Esecuzione dell'aggiornamento dei prezzi in un thread separato (necessario per la corretta visualizzazione del dialog)
    thread = threading.Thread(target=update_prices_threaded, args=(dialog, update_all))
    thread.start()

    dialog.wait_window()


def update_products_to_view():
    """
    Aggiorna la lista dei prodotti da visualizzare in base al testo inserito nella barra di ricerca
    """
    global products_to_view

    # Resetta i filtri mantenendo lo stato corrente della barra di ricerca
    reset_filters(reset_search_bar=False)

    search_text = search_entry.get()

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
            elif isinstance(widget, ttk.Entry):
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


def sort_by_column(col_idx):
    """
    Ordinamento dei prodotti visualizzati nella TreeView in base alla colonna selezionata
    """
    global products_to_view

    column_name = columns[col_idx]

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


def click(event):
    """
    Selezione prodotto con il tasto sinistro del mouse e multiselezione con ctrl + tasto sinistro del mouse
    Deseleziona tutti i prodotti se si seleziona qualcosa di diverso da un prodotto nella TreeView
    """
    global current_index, click_index

    products_in_tree_view = products_tree.get_children()
    selected_products = products_tree.selection()

    # Identifica il prodotto cliccato (basato sulla posizione y del click)
    identified_product_index = products_tree.identify_row(event.y)

    # Seleziona o deseleziona un prodotto in base a se è stato cliccato o meno
    if identified_product_index in products_in_tree_view:
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
        # Deseleziona solo se l'evento proviene dal widget della TreeView
        if event.widget == products_tree:
            products_tree.selection_remove(*selected_products)

            current_index = None


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
        if current_index == len(products_in_tree_view) - 1 and products_in_tree_view[current_index] not in selected_products:
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
        if current_index == 0 and products_in_tree_view[current_index] not in selected_products:
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

            current_index = None


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

    def update_buttons_state():
        """
        Aggiornamento dello stato dei pulsanti in base al numero di prodotti selezionati
        """
        num_selected_products = len(products_tree.selection())

        if num_selected_products == 1:
            view_button["state"] = "normal"
            edit_button["state"] = "normal"
            remove_button["state"] = "normal"
            update_button["state"] = "normal"
        elif num_selected_products > 1:
            view_button["state"] = "disabled"
            edit_button["state"] = "disabled"
            remove_button["state"] = "normal"
            update_button["state"] = "normal"
        else:
            view_button["state"] = "disabled"
            edit_button["state"] = "disabled"
            remove_button["state"] = "disabled"
            update_button["state"] = "disabled"
            update_all_button["state"] = "normal" if products_to_view else "disabled"

    if is_possible_to_refresh_root:
        refresh_tree_view()

        update_buttons_state()

        # Chiama ricorsivamente la funzione dopo 500 millisecondi per creare un aggiornamento periodico della Root
        root.after(500, periodic_refresh_root)


def set_periodic_refresh_root(update=True):
    """
    Funzione principale che gestisce l'abilitazione o la disabilitazione del refresh periodico
    Se `update` è True, abilita i controlli, resettando i thread che monitorano i prodotti e avviando il refresh periodico
    Se `update` è False, disabilita i controlli e ferma i thread che monitorano i prodotti
    """
    def disable_controls():
        """
        Disabilita i controlli dell'interfaccia utente
        """
        add_button.config(state="disabled")
        view_button.config(state="disabled")
        edit_button.config(state="disabled")
        remove_button.config(state="disabled")
        update_button.config(state="disabled")
        update_all_button.config(state="disabled")
        search_entry.config(state="disabled")

    def enable_controls():
        """
        Abilita i controlli dell'interfaccia utente
        """
        add_button.config(state="normal")
        view_button.config(state="normal")
        edit_button.config(state="normal")
        remove_button.config(state="normal")
        update_button.config(state="normal")
        update_all_button.config(state="normal")
        search_entry.config(state="normal")

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
        enable_controls()
        reset_threads()
    else:
        is_possible_to_refresh_root = False
        disable_controls()
        stop_threads()


# Variabili globali
columns = (
    "Nome",
    "URL",
    "Prezzo",
    "Notifica",
    "Timer",
    "Timer Aggiornamento [s]",
    "Data Inserimento",
    "Data Ultima Modifica",
)

config_file = "config.json"

products_file = "products.json"
products = {}
products_to_view = {}

prices_file = "prices.json"
prices = {}
prices_graph_application = None

threads = {}
stop_events = {}

sort_state = {
    "column": None,
    "order": 0,  # 0: nessun ordinamento, 1: crescente, 2: decrescente
}

common_font = ("Arial", 10)

current_index = None

click_index = None

is_possible_to_refresh_root = True

# Interfaccia principale
root = tk.Tk()
root.title("Monitoraggio Prezzi Amazon")
root.minsize(1600, 500)
root.wm_state("zoomed")

limit_letters = (root.register(lambda s: len(s) <= 50), "%P") # Regola per limitare i caratteri da inserire

# Pulsanti
button_frame = ttk.Frame(root)
button_frame.pack(fill="x", padx=10, pady=(15, 0))

add_button = ttk.Button(button_frame, text="Aggiungi", command=open_add_product_dialog)
add_button.grid(row=2, column=0, padx=5, pady=5, sticky="we")

view_button = ttk.Button(button_frame, text="Visualizza", command=show_product_details, state="disabled")
view_button.grid(row=2, column=1, padx=5, pady=5, sticky="we")

edit_button = ttk.Button(button_frame, text="Modifica", command=open_edit_product_dialog, state="disabled")
edit_button.grid(row=2, column=2, padx=5, pady=5, sticky="we")

remove_button = ttk.Button(button_frame, text="Rimuovi", command=remove_products, state="disabled")
remove_button.grid(row=2, column=3, padx=5, pady=5, sticky="we")

ttk.Label(button_frame, text="", width=18).grid(row=2, column=4, padx=5, pady=5, sticky="we") # Spazio

update_button = ttk.Button(button_frame, text="Aggiorna Selezionati", command=lambda: open_progress_dialog(False), state="disabled")
update_button.grid(row=2, column=5, padx=5, pady=5, sticky="e")

update_all_button = ttk.Button(button_frame, text="Aggiorna Tutti", command=lambda: open_progress_dialog(), state="disabled")
update_all_button.grid(row=2, column=6, padx=5, pady=5, sticky="e")

# Barra di ricerca
search_frame = ttk.Frame(root)
search_frame.pack(fill="x", padx=5, pady=0)

ttk.Label(search_frame, text="Ricerca Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

search_entry = ttk.Entry(search_frame, width=80, font=common_font, validate="key", validatecommand=limit_letters)
search_entry.grid(row=0, column=1, padx=10, pady=10, sticky="we")
search_entry.bind("<KeyRelease>", lambda e: update_products_to_view())
search_entry.bind("<Button-3>", lambda e: show_text_menu(e, search_entry))

# Lista prodotti
frame_products_tree = tk.Frame(root)
frame_products_tree.pack(fill="both", expand=True, padx=(15, 10), pady=(10, 0))

products_tree = ttk.Treeview(frame_products_tree, columns=columns, show="headings", selectmode="none")
products_tree.pack(side="left", fill="both", expand=True)

for idx, col in enumerate(columns):
    products_tree.heading(col, text=col, anchor="center", command=lambda _idx=idx: sort_by_column(_idx))
    products_tree.column(col, width=80 if col in ["Notifica"] else 200, anchor="center" if col in ["Prezzo", "Notifica", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica"] else "w")

scrollbar = ttk.Scrollbar(frame_products_tree, orient="vertical", command=products_tree.yview)
scrollbar.pack(side="right", fill="y")
products_tree.configure(yscrollcommand=scrollbar.set)

# Footer
frame_footer = tk.Frame(root)
frame_footer.pack(side="bottom", fill="x", padx=(20, 40), pady=2)

creator_label = tk.Label(frame_footer, text="Prodotto da Vincenzo Salvati", font=("Arial", 8))
creator_label.pack(side="right")

# Menu tasto destro
single_selection_menu = tk.Menu(root, tearoff=0)
single_selection_menu.add_command(label="Visualizza prodotto", command=show_product_details)
single_selection_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog)
single_selection_menu.add_command(label="Rimuovi prodotto", command=remove_products)

multi_selection_menu = tk.Menu(root, tearoff=0)
multi_selection_menu.add_command(label="Rimuovi selezionati", command=remove_products)
multi_selection_menu.add_command(label="Aggiorna selezionati", command=lambda: open_progress_dialog(False))

# Definizione eventi root e product_tree
root.bind("<Control-a>", select_all_products)

products_tree.bind("<Button-1>", click)
products_tree.bind("<Double-1>", show_product_details)
products_tree.bind("<Return>", show_product_details)
products_tree.bind("<Shift-Button-1>", shift_click)
products_tree.bind("<Down>", arrow_navigation_and_shift_arrow)
products_tree.bind("<Up>", arrow_navigation_and_shift_arrow)
products_tree.bind("<Button-3>", show_tree_view_menu)

# Carica i dati
load_products_data()
load_prices_data()

# Avvio interfaccia
periodic_refresh_root()
root.mainloop()
