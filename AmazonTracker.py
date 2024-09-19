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


log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger('logger')
logger.setLevel(logging.WARNING)
logger_handler = logging.FileHandler(os.path.join(log_dir, 'logger.log'))
logger_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(logger_handler)


def load_config():
    """
    Carica le impostazioni di configurazione dal file 'config.json'.
    
    Returns:
        tuple: Contiene le credenziali e le informazioni necessarie.
    
    Raises:
        SystemExit: Se si verifica un errore nel caricamento del file di configurazione.
    """
    config_file = "config.json"

    # Controlla se il file di configurazione esiste
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as file:
                # Carica le impostazioni dal file JSON
                config = json.load(file)
                return (config['sender_email'], config['sender_password'],
                        config['receiver_email'], config['url_telegram'], 
                        config['chat_id_telegram'])
        
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
    Invia un'email utilizzando le credenziali fornite nella configurazione.
    
    Args:
        subject (str): Oggetto dell'email.
        body (str): Corpo dell'email.
        email_to_notify (str): Indirizzo email del destinatario.
    """
    from_email, from_password, _, _, _ = load_config()

    # Crea il messaggio email
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = email_to_notify
    msg['Subject'] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Connessione al server SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, from_password)
        server.sendmail(from_email, email_to_notify, msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f"Impossibile inviare l'email: {e}")


def send_notification(subject, body):
    """
    Invia una notifica via email e Telegram.
    
    Args:
        subject (str): Oggetto della notifica.
        body (str): Corpo della notifica.
    """
    _, _, recipient_email, url_telegram, chat_id_telegram = load_config()

    # Invia notifica via email
    send_email(subject, body, recipient_email)

    # Invia notifica via Telegram
    try:
        payload = {
            "chat_id": chat_id_telegram,
            "text": body
        }
        response = requests.post(url_telegram, data=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Impossibile inviare il messaggio Telegram: {e}")


def calculating_suggestion(all_prices, current_price, price_average, price_minimum, price_maximum):
        """
        Calcola un suggerimento basato sui prezzi storici e sul prezzo corrente.

        Args:
            all_prices (list): Lista di prezzi storici del prodotto.
            current_price (float): Prezzo corrente del prodotto.
            price_average (float): Prezzo medio storico.
            price_minimum (float): Prezzo minimo storico.
            price_maximum (float): Prezzo massimo storico.

        Returns:
            tuple: Un suggerimento testuale e un colore associato.
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


def reset_filters(reset_search_bar=True):
    """
    Ripristina i filtri dei prodotti e riordina l'elenco dei prodotti visualizzati.
    
    Args:
        reset_search_bar (bool): Se True, svuota la barra di ricerca.
    """
    global products_to_view, sort_state

    # Ripristina lo stato di ordinamento
    sort_state = {
        'column': None,
        'order': 0
    }

    # Mappa delle colonne ai relativi criteri di ordinamento
    column_key_map = {
        'Nome': lambda item: item[0].lower(),
        'URL': lambda item: item[1]['url'].lower(),
        'Prezzo': lambda item: item[1]['price'] if isinstance(item[1]['price'], (int, float)) else float('inf'),
        'Notifica': lambda item: item[1]['notify'],
        'Timer': lambda item: item[1]['timer'],
        'Timer Aggiornamento [s]': lambda item: item[1]['timer_refresh'],
        'Data Inserimento': lambda item: item[1]['date_added'],
        'Data Ultima Modifica': lambda item: item[1]['date_edited']
    }

    # Ordina gli elementi in base alla data dell'ultima modifica
    items = list(products_to_view.items())
    items.sort(key=column_key_map['Data Ultima Modifica'])

    # Aggiorna il dizionario dei prodotti da visualizzare
    products_to_view = {name: details for name, details in items}

    # Aggiorna le intestazioni delle colonne nel widget Treeview
    for column in columns:
        products_tree.heading(column, text=column, anchor='center')

    # Se richiesto, svuota la barra di ricerca
    if reset_search_bar:
        search_entry.delete(0, tk.END)


def get_price(url):
    """
    Estrae il prezzo di un prodotto dalla pagina web specificata.

    Args:
        url (str): URL della pagina web del prodotto.

    Returns:
        float: Prezzo del prodotto in formato numerico, se trovato.
        None: Se si verifica un errore durante l'estrazione del prezzo.
    """
    # Intestazioni della richiesta HTTP per simulare un browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9",
    }

    try:
        # Effettua la richiesta HTTP
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parsing del contenuto HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Trova l'elemento che contiene il titolo del prodotto
        title_element = soup.find("span", id="productTitle")
        
        if title_element is None:
            raise ValueError("Titolo del prodotto non trovato")

        # Trova il contenitore del titolo
        title_container = title_element.find_parent()

        # Trova l'elemento del prezzo immediatamente dopo il titolo
        price_element = title_container.find_next("span", class_="aok-offscreen")

        if price_element is None:
            raise ValueError("Elemento prezzo non trovato sotto il titolo")

        # Estrae e pulisce il testo del prezzo
        price_text = price_element.get_text().strip()
        match = re.search(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})?', price_text)
        
        if match:
            # Converte il prezzo in formato numerico
            price_value = match.group(0).replace(".", "").replace(",", ".")
            return float(price_value)
        else:
            raise ValueError("Prezzo non trovato nel testo")

    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP di get_price: {e}")
        return None
    except Exception as e:
        logger.error(f"Errore in get_price: {e}")
        return None


def get_last_price(name):
    """
    Ottiene l'ultimo prezzo registrato per un dato prodotto.

    Args:
        name (str): Nome del prodotto per il quale ottenere l'ultimo prezzo.

    Returns:
        float: Ultimo prezzo registrato del prodotto se trovato.
        None: Se il prodotto non è presente nei dati dei prezzi.
    """
    # Verifica se il prodotto è presente nei dati dei prezzi
    if name in prices:
        # Trova l'ultima voce basata sulla data
        last_entry = max(prices[name], key=lambda x: x['date'])

        return last_entry['price']
    else:
        return None


def start_tracking(name, url):
    """
    Avvia o riavvia il monitoraggio del prezzo per un dato prodotto.
    
    Args:
        name (str): Nome del prodotto da monitorare.
        url (str): URL della pagina del prodotto.
    """
    def track_loop(name, url):
        """
        Ciclo principale di monitoraggio che controlla il prezzo e invia notifiche.

        Args:
            name (str): Nome del prodotto da monitorare.
            url (str): URL della pagina del prodotto.
        """
        def check_price_and_notify(name, url):
            """
            Controlla il prezzo attuale e invia notifiche se il prezzo è cambiato.

            Args:
                name (str): Nome del prodotto.
                url (str): URL della pagina del prodotto.
            """
            # Ottieni il prezzo attuale
            current_price = get_price(url)

            if current_price is None:
                logger.warning(f"Non trovato il prezzo di {name} sulla pagina {url}")
                return
            
            if products[name]['notify']:
                # Ottieni il prezzo precedente
                previous_price = get_last_price(name)

                # Ottieni i prezzi storici
                historical_prices = prices.get(name, [])
                
                # Calcoli sui prezzi storici
                all_prices = [entry['price'] for entry in historical_prices if isinstance(entry['price'], (int, float))]
                if all_prices:
                    average_price = round(statistics.mean(all_prices), 2)
                    price_minimum = min(all_prices)
                    price_maximum = max(all_prices)
                else:
                    average_price = price_minimum = price_maximum = current_price

                text_suggestion, _ = calculating_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)

                subject = "Prezzo in calo!"
                body = (f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n" +
                        f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n" +
                        f"Acquista ora: {products[name]['url']}")
                
                if previous_price is None:
                    logger.warning(f"Non trovato il prezzo di {name} nelle liste")
                    return

                # Invia notifiche se il prezzo attuale è inferiore al prezzo precedente
                if current_price < previous_price:
                    send_notification(subject=subject, body=body)
                
                # Controlla se il prezzo è al di sotto delle soglie specificate e invia email
                for key, value in products[name]['emails_and_thresholds'].items():
                    value_to_compare = previous_price
                    subject_to_send = subject
                    body_to_send = body

                    if value != 0.0:
                        value_to_compare = value
                        subject_to_send = "Prezzo inferiore alla soglia indicata!"
                        body_to_send = (f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.\n" +
                                        f"Il costo attuale è {current_price}€.\n\n" +
                                        f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n" +
                                        f"Acquista ora: {products[name]['url']}")
                    
                    if current_price < value_to_compare:
                        send_email(subject=subject_to_send, body=body_to_send, email_to_notify=key)

            # Aggiorna il prezzo del prodotto e salva i dati
            products[name]['price'] = current_price
            save_prices_data(name, products[name]['price'])
            save_data()
            
        # Ciclo di monitoraggio
        while not stop_events[name].is_set():  # Continua finché l'evento non è settato
            if stop_events[name].wait(products[name]['timer_refresh']):
                break  # Esce immediatamente se l'evento è settato durante il wait
            check_price_and_notify(name, url)
            products[name]['timer'] = time.time()
            reset_filters()

        logger.info(f"Monitoraggio di '{name}' fermato")
        threads.pop(name, None)

    global threads, stop_events  # Dichiarazione delle variabili globali

    # Se c'è già un thread attivo, fermalo prima di avviarne uno nuovo
    if name in threads and threads[name].is_alive():
        logger.info(f"Fermando il monitoraggio precedente di '{name}'...")
        stop_events[name].set() # Segnala al thread corrente di fermarsi
        threads[name].join(timeout=1) # Aspetta che il thread corrente termini

    # Crea un nuovo evento di stop e avvia un nuovo thread
    stop_events[name] = threading.Event()  # Crea un nuovo evento per il nuovo thread
    timer_thread = threading.Thread(target=track_loop, args=(name, url,), daemon=True)
    threads[name] = timer_thread
    timer_thread.start()

    logger.info(f"Avviato il monitoraggio per '{name}' ({url}) con un nuovo timer")


def load_data():
    """
    Carica i dati dei prodotti dal file JSON e avvia il monitoraggio per ogni prodotto.
    """
    global products, products_to_view

    # Verifica se il file dei dati dei prodotti esiste
    if os.path.exists(products_file):
        try:
            # Legge i dati dal file JSON
            with open(products_file, "r") as file:
                products = json.load(file)

                # Verifica la struttura dei dati e avvia il monitoraggio
                for name in products:
                    if not isinstance(products[name], dict):
                        raise Exception("Ogni elemento nel file JSON dei dati articoli deve essere un dizionario")

                    url = products[name].get("url")

                    if not url:
                        raise Exception("Ogni prodotto deve avere un 'url'")

                    # Avvia il monitoraggio per il prodotto
                    start_tracking(name, url)

                # Imposta i dati dei prodotti da visualizzare
                products_to_view = products

                logger.info("Dati dei prodotti caricati correttamente")

        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati articoli: {e}")
            messagebox.showerror("Attenzione", "Errore durante il caricamento dei dati articoli")
            exit()
    else:
        logger.warning(f"File dei dati articoli '{products_file}' non trovato")
        messagebox.showwarning("Attenzione", f"File dei dati articoli '{products_file}' non trovato")


def save_data():
    """
    Salva i dati dei prodotti nel file JSON e aggiorna la vista dei prodotti.
    """
    try:
        global products_to_view

        # Salva i dati dei prodotti nel file JSON
        with open(products_file, "w") as file:
            json.dump(products, file, indent=4)

        # Aggiorna i dati da visualizzare
        products_to_view = products

        logger.info("Dati articoli salvati con successo")

    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati articoli: {e}")


def load_prices_data():
    """
    Carica i dati di monitoraggio dei prezzi dal file JSON.
    """
    global prices

    # Verifica se il file dei dati di monitoraggio dei prezzi esiste
    if os.path.exists(prices_file):
        try:
            # Legge i dati dal file JSON
            with open(prices_file, "r") as file:
                prices = json.load(file)

                # Verifica che ogni elemento sia una lista
                for name in prices:
                    if not isinstance(prices[name], list):
                        raise Exception("Ogni elemento nel file JSON dei dati monitoraggio prezzi deve essere una lista")

                logger.info("Dati monitoraggio prezzi caricati correttamente")

        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati monitoraggio prezzi: {e}")
            messagebox.showerror("Attenzione", "Errore durante il caricamento dei dati monitoraggio prezzi")
            exit()
    else:
        logger.warning(f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")
        messagebox.showwarning("Attenzione", f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")


def save_prices_data(name, price):
    """
    Salva l'aggiornamento del prezzo per un prodotto nel file JSON.

    Args:
        name (str): Nome del prodotto.
        price (float): Prezzo aggiornato del prodotto.
    """
    # Ottieni la data e l'ora corrente
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Crea un dizionario per la voce di prezzo
    price_entry = {
        "price": price,
        "date": current_time
    }

    # Aggiungi l'aggiornamento dei prezzi al prodotto
    if name not in prices:
        prices[name] = []

    prices[name].append(price_entry)

    # Salva i dati aggiornati nel file JSON
    try:
        with open(prices_file, 'w') as file:
            json.dump(prices, file, indent=4)

        logger.info(f"Salvato aggiornamento prezzo per {name}: {price}€ al {current_time}")

    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati monitoraggio prezzi: {e}")


def center_window(window):
    """
    Centra la finestra specificata sullo schermo.

    Args:
        window (tk.Tk): Finestra Tkinter da centrare.
    """
    # Aggiorna le dimensioni della finestra per ottenere le dimensioni corrette
    window.update_idletasks()
    
    # Ottieni le dimensioni della finestra
    width = window.winfo_width()
    height = window.winfo_height()
    
    # Calcola le coordinate per centrare la finestra
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    # Imposta la geometria della finestra con le nuove coordinate
    window.geometry(f'{width}x{height}+{x}+{y}')


def show_text_menu(event, widget, onlyRead=False):
    # Funzione per controllare se c'è testo selezionato
    def is_text_selected(widget):
        try:
            if isinstance(widget, tk.Text):
                return widget.tag_ranges(tk.SEL) != ()
            elif isinstance(widget, ttk.Entry):
                return widget.selection_present()
        except tk.TclError:
            return False
        return False

    # Funzione per controllare se c'è testo negli appunti
    def is_clipboard_available():
        try:
            return bool(root.clipboard_get())
        except tk.TclError:
            return False

    # Funzione per copiare il testo di una Label o del widget
    def copy_text(widget):
        try:
            if isinstance(widget, tk.Label):
                root.clipboard_clear()
                root.clipboard_append(widget.cget("text"))  # Copia il testo della label
            else:
                widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    # Funzione per tagliare il testo (solo per Entry e Text)
    def cut_text(widget):
        try:
            widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    # Funzione per incollare il testo (solo per Entry e Text)
    def paste_text(widget):
        try:
            widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    text_menu = tk.Menu(root, tearoff=0)

    if onlyRead:
        # Per le Label, abilitiamo solo la copia
        if is_text_selected(widget):
            text_menu.add_command(label="Copia", command=lambda: copy_text(widget))
        else:
            text_menu.add_command(label="Copia", state="disabled")
        text_menu.add_command(label="Taglia", state="disabled")
        text_menu.add_command(label="Incolla", state="disabled")
    else:
        # Controllo se c'è testo selezionato per abilitare/disabilitare Taglia e Copia
        if is_text_selected(widget):
            text_menu.add_command(label="Taglia", command=lambda: cut_text(widget))
            text_menu.add_command(label="Copia", command=lambda: copy_text(widget))
        else:
            text_menu.add_command(label="Taglia", state="disabled")
            text_menu.add_command(label="Copia", state="disabled")

        # Controllo se c'è testo negli appunti per abilitare/disabilitare Incolla
        if is_clipboard_available():
            text_menu.add_command(label="Incolla", command=lambda: paste_text(widget))
        else:
            text_menu.add_command(label="Incolla", state="disabled")

    # Mostra il menu contestuale
    text_menu.tk_popup(event.x_root, event.y_root)


def open_add_product_dialog():
    """
    Apre una finestra di dialogo per aggiungere un nuovo prodotto con URL e impostare altre opzioni.
    """
    def on_entry_focus_in(event):
        """
        Mostra la Listbox dei suggerimenti quando l'Entry riceve il focus.
        """
        update_suggestions()

    def on_entry_focus_out(event):
        """
        Nasconde la Listbox dei suggerimenti quando l'Entry perde il focus.
        """
        listbox_suggestions.place_forget()

    def update_suggestions(*args):
        """
        Aggiorna la Listbox dei suggerimenti in base al testo digitato.
        """
        # Ottieni il testo digitato e rimuovi spazi bianchi
        typed_text = name_entry_var.get().strip().lower()
        listbox_suggestions.delete(0, tk.END)        

        if typed_text:
            # Trova i nomi dei prodotti che corrispondono al testo digitato
            matching_suggestions = [name for name in prices.keys() if typed_text in name.lower()]

            listbox_suggestions.insert(tk.END, name_entry.get())
            for suggestion in matching_suggestions:
                listbox_suggestions.insert(tk.END, suggestion)
            
            # Configura l'altezza della Listbox e la posiziona sotto l'Entry
            listbox_suggestions.config(height=min(len(matching_suggestions), 5))
            x = name_entry.winfo_x()
            y = name_entry.winfo_y() + name_entry.winfo_height()
            listbox_frame.place(x=x, y=y, anchor="nw")
            listbox_suggestions.lift()

        else:
            listbox_frame.place_forget()

    def on_select_suggestion(event):
        """
        Gestisce la selezione di un suggerimento dalla Listbox.
        """
        selection = listbox_suggestions.curselection()
        if selection:
            selected_name = listbox_suggestions.get(selection[0])
            name_entry.delete(0, tk.END)
            name_entry.insert(0, selected_name)
            listbox_suggestions.place_forget()

    def open_advanced_dialog():
        """
        Apre una finestra di dialogo per configurare le email e le soglie di notifica.
        """
        def add_email_threshold():
            """
            Aggiunge una nuova email e soglia alla lista.
            """
            email = email_entry.get().strip()
            threshold = threshold_entry.get().strip()

            if not email:
                messagebox.showwarning("Attenzione", "Compila l'email!")
                return
            
            if not threshold:
                threshold = 0.0

            try:
                threshold = float(threshold)

                if threshold < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0.")
                return

            if email in emails_and_thresholds:
                messagebox.showwarning("Attenzione", "L'email è già presente nella tabella.")
                return

            emails_and_thresholds[email] = threshold

            update_table()

            email_entry.delete(0, "end")
            threshold_entry.delete(0, "end")

        def update_table():
            """
            Aggiorna la tabella con le email e le soglie.
            """
            table.delete(*table.get_children())
            for key, value in sorted(emails_and_thresholds.items()):
                table.insert("", "end", iid=key, values=(key, str(value)+"€"))

        def show_context_menu(event):
            """
            Mostra il menu contestuale al clic destro sulla tabella.
            """
            item = table.identify_row(event.y)
            if not item:
                return
            table.selection_set(item)
            context_menu.post(event.x_root, event.y_root)

        def remove_email():
            """
            Rimuove l'email selezionata dalla tabella.
            """
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            del emails_and_thresholds[email]
            update_table()

        def modify_threshold():
            """
            Modifica la soglia per l'email selezionata.
            """
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            new_threshold = simpledialog.askstring("Modifica Soglia", f"Soglia di notifica per '{email}':")
            new_threshold = new_threshold.replace(" ", "")
            if new_threshold == "":
                new_threshold = 0.0
            try:
                emails_and_thresholds[email] = float(new_threshold)
                update_table()
            except:
                messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")
        
        def validate_timer_input(input_value):
            """
            Verifica se il valore di input del timer è valido.
            """
            return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

        def on_timer_change(*args):
            """
            Aggiorna il valore del timer quando l'utente modifica l'input.
            """
            global timer_refresh

            value = timer_entry.get()

            if value.isdigit():
                timer_refresh = int(value)
            else:
                timer_refresh = 0

            if timer_refresh == 0:
                timer_refresh = 1800
                timer_entry.delete(0, "end")
                timer_entry.insert(0, "1800")

        # Crea la finestra di dialogo avanzata
        advanced_dialog = tk.Toplevel(root)
        advanced_dialog.title("Aggiungi e-mail e soglia notifica")
        advanced_dialog.resizable(False, False)

        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))

        ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(lambda s: s.isdigit() or s in ['.', '-']), '%S'))
        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        # Tabella per mostrare email e soglie aggiunte
        columns = ("Email", "Soglia")
        table = ttk.Treeview(container, columns=columns, show="headings")
        table.grid(row=3, column=0, columnspan=2, pady=10, sticky="nsew")
        table.heading("Email", text="Email")
        table.heading("Soglia", text="Soglia")
        table.column("Email", width=200)
        table.column("Soglia", width=100)

        # Creazione della scrollbar verticale
        vsb = ttk.Scrollbar(container, orient="vertical", command=table.yview)
        vsb.grid(row=3, column=2, sticky="ns")

        # Associare la scrollbar alla Treeview
        table.configure(yscrollcommand=vsb.set)

        # Menu contestuale
        context_menu = tk.Menu(advanced_dialog, tearoff=0)
        context_menu.add_command(label="Modifica Soglia", command=modify_threshold)
        context_menu.add_command(label="Rimuovi Email", command=remove_email)

        # Binding per il tasto destro
        table.bind("<Button-3>", show_context_menu)

        update_table()

        # Campo del timer posizionato sotto la tabella
        ttk.Label(container, text="Timer [s]:").grid(row=4, column=0, padx=10, pady=10, sticky="we")
        timer_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(validate_timer_input), '%P'))
        timer_entry.grid(row=4, column=1, padx=10, pady=10, sticky='w')
        timer_entry.insert(0, timer_refresh)
        timer_entry.bind('<KeyRelease>', on_timer_change)
        timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))

        advanced_dialog.transient(root)
        advanced_dialog.grab_set()
        center_window(advanced_dialog)

    def add_product(name, url):
        """
        Aggiunge un nuovo prodotto e avvia il monitoraggio.
        
        Args:
            name (str): Nome del prodotto.
            url (str): URL del prodotto.
        """
        if not name or not url:
                messagebox.showwarning("Attenzione", "Compila tutti i campi!")
                return False

        # Verifica se il prodotto esiste già
        for product_name in products:
            if name == product_name:
                messagebox.showwarning("Attenzione", "Il nome del prodotto è già presente!\nCambia il nome")
                return False

            if url == products[product_name]['url']:
                messagebox.showwarning("Attenzione", "Questo articolo è già in monitoraggio!\nCambia url")
                return False

        current_price = get_price(url)

        if current_price is None:                
            current_price = "Aggiorna o verifica url: - "
            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica url")
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        products[name] = {
            "url": url,
            "price": current_price,
            "notify": notify.get(),
            "timer": time.time(),
            "timer_refresh": timer_refresh,
            "date_added": now,
            "date_edited": now,
            "emails_and_thresholds": emails_and_thresholds
        }
        
        save_data()
        save_prices_data(name, products[name]['price'])

        start_tracking(name, url)

        reset_filters()

        logger.info(f"Prodotto '{name}' aggiunto con successo")
    
        add_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    emails_and_thresholds = {}
    timer_refresh = 1800
    notify = tk.BooleanVar(value=True)

    # Crea la finestra di dialogo per aggiungere un prodotto
    add_product_dialog = tk.Toplevel(root)
    add_product_dialog.title("Aggiungi Prodotto")
    add_product_dialog.resizable(False, False)

    container = ttk.Frame(add_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    name_entry_var = tk.StringVar()
    name_entry_var.trace_add('write', update_suggestions)

    name_entry = ttk.Entry(container, width=80, font=common_font, textvariable=name_entry_var, validate='key', validatecommand=limit_letters)
    name_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
    name_entry.bind("<Button-3>", lambda e: show_text_menu(e, name_entry))

    # Frame per Listbox e Scrollbar
    listbox_frame = ttk.Frame(add_product_dialog)
    listbox_frame.place_forget()

    listbox_suggestions = tk.Listbox(listbox_frame, width=80)
    listbox_suggestions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)

    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox_suggestions.yview)
    scrollbar.pack(side="right", fill="y")

    listbox_suggestions.config(yscrollcommand=scrollbar.set)

    # Associa eventi di movimento del mouse
    name_entry.bind("<FocusIn>", on_entry_focus_in)
    name_entry.bind("<FocusOut>", on_entry_focus_out)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    # Crea un frame per ospitare il widget Text e la scrollbar
    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)
    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")

    # Configura il widget Text per usare la scrollbar
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    # Bottone per aprire la finestra di dialogo avanzata
    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")

    # Bottone per aggiungere il prodotto
    ttk.Button(container, text="Aggiungi", command=lambda: add_product(name_entry.get().strip().lower(), url_text.get("1.0", "end-1c").strip())).grid(row=3, column=1, pady=10, sticky="e")

    add_product_dialog.transient(root)
    add_product_dialog.grab_set()
    center_window(add_product_dialog)


def open_edit_product_dialog():
    """
    Apre una finestra di dialogo per modificare l'URL di un prodotto esistente e impostare altre opzioni.
    """
    def open_advanced_dialog():
        """
        Apre una finestra di dialogo per configurare le email e le soglie di notifica avanzate.
        """
        def add_email_threshold():
            """
            Aggiunge una nuova email e soglia alla lista.
            """
            email = email_entry.get().strip()
            threshold = threshold_entry.get().strip()

            if not email:
                messagebox.showwarning("Attenzione", "Compila l'email!")
                return
            
            if not threshold:
                threshold = 0.0

            try:
                threshold = float(threshold)
                if threshold < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")
                return

            if email in emails_and_thresholds:
                messagebox.showwarning("Attenzione", "L'email è già presente nella tabella")
                return

            emails_and_thresholds[email] = threshold
            update_table()

            email_entry.delete(0, "end")
            threshold_entry.delete(0, "end")

        def update_table():
            """
            Aggiorna la tabella con le email e le soglie.
            """
            table.delete(*table.get_children())
            for key, value in sorted(emails_and_thresholds.items()):
                table.insert("", "end", iid=key, values=(key, str(value) + "€"))

        def show_context_menu(event):
            """
            Mostra il menu contestuale al clic destro sulla tabella.
            """
            item = table.identify_row(event.y)
            if not item:
                return
            table.selection_set(item)
            context_menu.post(event.x_root, event.y_root)

        def remove_email():
            """
            Rimuove l'email selezionata dalla tabella.
            """
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            del emails_and_thresholds[email]
            update_table()

        def modify_threshold():
            """
            Modifica la soglia per l'email selezionata.
            """
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            new_threshold = simpledialog.askstring("Modifica Soglia", f"Soglia di notifica per '{email}':")
            new_threshold = new_threshold.replace(" ", "")
            if new_threshold == "":
                new_threshold = 0.0
            try:
                emails_and_thresholds[email] = float(new_threshold)
                update_table()
            except:
                messagebox.showwarning("Attenzione", "Inserisci una soglia valida (numerica) oppure 0")

        def validate_timer_input(input_value):
            """
            Verifica se il valore di input del timer è valido.
            """
            return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

        def on_timer_change(*args):
            """
            Aggiorna il valore del timer quando l'utente modifica l'input.
            """
            global timer_refresh

            value = timer_entry.get()

            if value.isdigit():
                timer_refresh = int(value)
            else:
                timer_refresh = 0

            if timer_refresh == 0:
                timer_refresh = 1800
                timer_entry.delete(0, "end")
                timer_entry.insert(0, "1800")

        # Crea la finestra di dialogo avanzata
        advanced_dialog = tk.Toplevel(root)
        advanced_dialog.title("Aggiungi e-mail e soglia notifica")
        advanced_dialog.resizable(False, False)

        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))

        ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(lambda s: s.isdigit() or s in ['.', '-']), '%S'))
        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        # Tabella per mostrare email e soglie aggiunte
        columns = ("Email", "Soglia")
        table = ttk.Treeview(container, columns=columns, show="headings")
        table.grid(row=3, column=0, columnspan=2, pady=10, sticky="nsew")
        table.heading("Email", text="Email")
        table.heading("Soglia", text="Soglia")
        table.column("Email", width=200)
        table.column("Soglia", width=100)

        # Creazione della scrollbar verticale
        vsb = ttk.Scrollbar(container, orient="vertical", command=table.yview)
        vsb.grid(row=3, column=2, sticky="ns")

        # Associare la scrollbar alla Treeview
        table.configure(yscrollcommand=vsb.set)

        # Menu contestuale
        context_menu = tk.Menu(advanced_dialog, tearoff=0)
        context_menu.add_command(label="Modifica Soglia", command=modify_threshold)
        context_menu.add_command(label="Rimuovi Email", command=remove_email)

        # Binding per il tasto destro
        table.bind("<Button-3>", show_context_menu)

        ttk.Label(container, text="Timer [s]:").grid(row=4, column=0, padx=10, pady=10, sticky="we")
        timer_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(validate_timer_input), '%P'))
        timer_entry.grid(row=4, column=1, padx=10, pady=10, sticky='w')
        timer_entry.insert(0, timer_refresh)
        timer_entry.bind('<KeyRelease>', on_timer_change)
        timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))

        update_table()

        advanced_dialog.transient(root)
        advanced_dialog.grab_set()
        center_window(advanced_dialog)

    def edit_product(name, current_url, new_url):
        """
        Gestisce la modifica delle informazioni di un prodotto.
        
        Args:
            name (str): Nome del prodotto.
            current_url (str): URL attuale del prodotto.
            new_url (str): Nuovo URL del prodotto.
        """
        if not new_url:
                messagebox.showwarning("Attenzione", "Compila l'URL!")
                return False

        if current_url != new_url:
            for product_name in products:
                if new_url == products[product_name]['url']:
                    messagebox.showwarning("Attenzione", "Questo articolo è già in monitoraggio!\nCambia l'URL")
                    return False

        new_price = get_price(new_url)

        if new_price is None:                
            products[name]['price'] = "Aggiorna o verifica l'URL: - "
            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica l'URL")
            logger.warning(f"Sul prodotto {name} non è stato trovato il prezzo sulla pagina " + products[name]['url'])
        else:
            products[name]['price'] = new_price

        products[name]['url'] = new_url
        products[name]['notify'] = notify.get()
        products[name]['timer'] = time.time()
        products[name]['timer_refresh'] = timer_refresh
        products[name]['date_edited'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        products[name]['emails_and_thresholds'] = emails_and_thresholds

        save_data()
        save_prices_data(name, products[name]['price'])

        start_tracking(name, new_url)

        reset_filters()

        logger.info(f"Prodotto '{name}' modificato con successo")

        edit_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    selected_item = products_tree.selection()[0]
    selected_name = products_tree.item(selected_item)['values'][0]
    selected_url = products[selected_name]['url']
    emails_and_thresholds = products[selected_name]['emails_and_thresholds']
    timer_refresh = products[selected_name]['timer_refresh']
    notify = tk.BooleanVar(value=products[selected_name]['notify'])

    # Crea la finestra di dialogo per modificare un prodotto
    edit_product_dialog = tk.Toplevel(root)
    edit_product_dialog.title("Modifica Prodotto")
    edit_product_dialog.resizable(False, False)

    container = ttk.Frame(edit_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
    
    # Creazione di un tk.Text per il testo selezionabile
    text_widget = tk.Text(container, font=common_font, height=1, width=80, wrap='none', bd=0, bg='white')
    text_widget.insert(tk.END, selected_name)
    text_widget.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    text_widget.bind("<Button-3>", lambda e: show_text_menu(e, text_widget, True))
    
    # Rendere il testo solo in lettura
    text_widget.config(state=tk.DISABLED)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
    
    # Crea un frame per ospitare il widget Text e la scrollbar
    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")
    
    # Crea il widget Text
    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)
    url_text.insert("1.0", selected_url)
    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))
    
    # Crea la scrollbar
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    
    # Configura il widget Text per usare la scrollbar
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    # Bottone per aprire la finestra di dialogo avanzata
    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")

    # Bottone per salvare le modifiche
    ttk.Button(container, text="Salva", command=lambda: edit_product(selected_name, selected_url, url_text.get("1.0", "end-1c").strip())).grid(row=3, column=1, pady=10, sticky="e")

    edit_product_dialog.transient(root)
    edit_product_dialog.grab_set()
    center_window(edit_product_dialog)


def remove_products():
    """
    Rimuove i prodotti selezionati dalla lista e ferma il monitoraggio.
    """
    def stop_tracking(name):
        """
        Ferma il monitoraggio per un prodotto specificato e rimuove il relativo thread.
        
        Args:
            name (str): Nome del prodotto da fermare.
        """
        if name in stop_events:
            stop_events[name].set()  # Setta l'evento di stop per fermare il monitoraggio

        if name in threads:
            threads[name].join(timeout=1)  # Attende la terminazione del thread

        # Rimuove l'evento di stop per questo prodotto
        if name in stop_events:
            del stop_events[name]

    global stop_events, threads

    # Recupera la selezione dell'utente
    selected = products_tree.selection()

    if not selected:
        logger.warning("Seleziona un prodotto dalla lista per rimuoverlo")
        return

    num_selected = len(selected)

    # Chiede conferma all'utente
    response = messagebox.askyesno(
        "Conferma rimozione",
        f"Sei sicuro di voler rimuovere i {num_selected} prodotti selezionati?" if num_selected > 1 else f"Sei sicuro di voler rimuovere il prodotto selezionato?"
    )

    # Se l'utente conferma, procedi con la rimozione
    if response:
        # Resetta i filtri per riflettere la rimozione del prodotto
        reset_filters()

        for name in selected:
            if name in products:
                # Rimuove il prodotto dalla lista
                del products[name]

                # Salva i dati dopo la rimozione
                save_data()
                
                # Ferma il monitoraggio del prodotto
                stop_tracking(name)

                # Logga l'azione di rimozione
                logger.info(f"Prodotto '{name}' rimosso con successo")
            else:
                logger.warning(f"Il prodotto '{name}' non è presente nella lista")


def send_notification_and_email(name, prev_price, curr_price):
    """
    Invia notifiche via email quando il prezzo di un prodotto cambia.

    Args:
        name (str): Nome del prodotto.
        prev_price (float): Prezzo precedente del prodotto.
        curr_price (float): Prezzo corrente del prodotto.
    """
    # Definisce l'oggetto e il corpo della notifica principale
    historical_prices = prices.get(name, [])
    
    # Calcoli sui prezzi storici
    all_prices = [entry['price'] for entry in historical_prices if isinstance(entry['price'], (int, float))]
    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = curr_price

    text_suggestion, _ = calculating_suggestion(all_prices, curr_price, average_price, price_minimum, price_maximum)

    subject = "Prezzo in calo!"
    body = (f"Il prezzo dell'articolo '{name}' è sceso da {prev_price}€ a {curr_price}€.\n\n" +
            f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n" +
            f"Acquista ora: {products[name]['url']}")

    # Invia la notifica principale
    send_notification(subject=subject, body=body)

    # Controlla e invia notifiche per email agli utenti
    for email, threshold in products[name]['emails_and_thresholds'].items():
        # Imposta il valore di confronto e il messaggio da inviare
        value_to_compare = prev_price
        subject_to_send = subject
        body_to_send = body

        # Se è impostata una soglia, aggiorna i messaggi e il valore di confronto
        if threshold != 0.0:
            value_to_compare = threshold
            subject_to_send = "Prezzo inferiore alla soglia indicata!"
            body_to_send = (f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.\n" +
                            f"Il costo attuale è {curr_price}€.\n\n" +
                            f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n" +
                            f"Acquista ora: {products[name]['url']}")

        # Invia una notifica via email se il prezzo corrente è inferiore al valore di confronto
        if curr_price < value_to_compare:
            send_email(subject=subject_to_send, body=body_to_send, email_to_notify=email)


def open_progress_dialog(update_all = True):
    """
    Crea e mostra una finestra di dialogo modale con una barra di progresso per il processo di aggiornamento.
    """
    def update_prices_threaded(dialog, update_all = True):
        """
        Esegue l'aggiornamento dei prezzi in un thread separato e chiude la finestra di dialogo alla fine sbloccando la root.
        """
        def update_selected_prices(dialog):
            """
            Aggiorna i prezzi dei prodotti selezionati e notifica eventuali cambiamenti.
            """
            # Stop threads and stop update view
            set_enable_update(False)

            # Resetta i filtri (se presenti)
            reset_filters()

            # Ottieni i prodotti selezionati nella TreeView
            selected = products_tree.selection()

            if not selected:
                logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
                return

            # Inizializza barra di caricamento
            max_value = len(selected)
            dialog.progress_bar["maximum"] = max_value
            dialog.progress_bar["value"] = 0

            updated_products = []

            # Itera sui prodotti selezionati per aggiornare i prezzi
            for i, name in enumerate(selected):
                # Aggiorna il progresso
                dialog.progress_bar["value"] = i + 1
                dialog.progress_label.config(text=f"Aggiornamento di {i + 1}/{max_value}...")
                dialog.update_idletasks()  # Aggiorna l'interfaccia grafica

                current_price = get_price(products[name]['url'])

                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    
                    # Aggiorna il prodotto con un messaggio di errore
                    products[name]['price'] = "Aggiorna o verifica url: - "
                    products[name]['timer'] = time.time()
                    products[name]['date_edited'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    continue

                # Aggiorna il prezzo del prodotto
                products[name]['price'] = current_price
                products[name]['timer'] = time.time()
                products[name]['date_edited'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Ottieni il prezzo precedente del prodotto
                previous_price = get_last_price(name)

                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price, products[name]['notify']))

                # Salva i dati dei prezzi aggiornati
                save_prices_data(name, products[name]['price'])

            # Salva tutti i dati dei prodotti aggiornati
            save_data()

            # Mostra un messaggio di stato per i prodotti aggiornati
            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, prev_price, curr_price, notify in updated_products:
                    if curr_price < prev_price:
                        status_message += f"{name}: Prezzo calato da {prev_price}€ a {curr_price}€\n"
                        if notify:
                            send_notification_and_email(name, prev_price, curr_price)
                    elif curr_price > prev_price:
                        status_message += f"{name}: Prezzo aumentato da {prev_price}€ a {curr_price}€\n"
                    else:
                        status_message += f"{name}: Prezzo invariato a {curr_price}€\n"

                messagebox.showinfo("Aggiornamento", status_message)
                logger.info("I prodotti selezionati sono stati aggiornati")
            else:
                messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali nuovamente")
                logger.warning("Nessun prodotto selezionato è stato aggiornato")

            # Resume threads and resume update view
            set_enable_update()

        def update_all_prices(dialog):
            """
            Aggiorna i prezzi di tutti i prodotti e notifica eventuali cambiamenti.
            """
            # Stop threads and stop update view
            set_enable_update(False)

            # Resetta i filtri (se presenti)
            reset_filters()

            # Inizializza barra di caricamento
            max_value = len(products)
            dialog.progress_bar["maximum"] = max_value
            dialog.progress_bar["value"] = 0

            updated_products = []

            # Itera su tutti i prodotti per aggiornare i prezzi
            for i, name in enumerate(products):
                # Aggiorna il progresso
                dialog.progress_bar["value"] = i + 1
                dialog.progress_label.config(text=f"Aggiornamento di {i + 1}/{max_value}...")
                dialog.update_idletasks()  # Aggiorna l'interfaccia grafica

                current_price = get_price(products[name]['url'])

                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    
                    # Aggiorna il prodotto con un messaggio di errore
                    products[name]['price'] = "Aggiorna o verifica url: - "
                    products[name]['timer'] = time.time()
                    products[name]['date_edited'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    continue

                # Aggiorna il prezzo del prodotto
                products[name]['price'] = current_price
                products[name]['timer'] = time.time()
                products[name]['date_edited'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Ottieni il prezzo precedente del prodotto
                previous_price = get_last_price(name)

                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price, products[name]['notify']))

                # Salva i dati dei prezzi aggiornati
                save_prices_data(name, products[name]['price'])

            # Salva tutti i dati dei prodotti aggiornati
            save_data()

            # Mostra un messaggio di stato per i prodotti aggiornati
            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, prev_price, curr_price, notify in updated_products:
                    if curr_price < prev_price:
                        status_message += f"{name}: Prezzo calato da {prev_price}€ a {curr_price}€\n"
                        if notify:
                            send_notification_and_email(name, prev_price, curr_price)
                    elif curr_price > prev_price:
                        status_message += f"{name}: Prezzo aumentato da {prev_price}€ a {curr_price}€\n"
                    else:
                        status_message += f"{name}: Prezzo invariato a {curr_price}€\n"

                messagebox.showinfo("Aggiornamento", status_message)
                logger.info("Tutti i prodotti sono stati aggiornati")
            else:
                messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali tutti nuovamente")
                logger.warning("Nessun prodotto è stato aggiornato")

            # Resume threads and resume update view
            set_enable_update()

        try:
            if update_all:
                update_all_prices(dialog)
            else:
                update_selected_prices(dialog)
        finally:
            dialog.destroy()
            root.resizable(True, True)
            root.wm_attributes("-disabled", False)

    dialog = tk.Toplevel(root)
    dialog.grab_set()  # Impedisce l'interazione con la finestra principale

    # Rimuove completamente la barra del titolo (incluso il pulsante "X")
    dialog.overrideredirect(True)
    
    # Disabilita il ridimensionamento della finestra
    dialog.resizable(False, False)

    # Blocca qualsiasi tentativo di ridimensionare o spostare la finestra principale
    root.resizable(False, False)
    
    # Blocca lo spostamento della finestra principale
    root.wm_attributes("-disabled", True)

    width = 300
    height = 100
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    position_x = int((screen_width / 2) - (width / 2))
    position_y = int((screen_height / 2) - (height / 2))
    
    dialog.geometry(f"{width}x{height}+{position_x}+{position_y}")

    # Crea una barra di progresso e una label
    progress_label = tk.Label(dialog, text="Inizio aggiornamento...")
    progress_label.pack(pady=10)
    progress_bar = ttk.Progressbar(dialog, orient="horizontal", length=250, mode="determinate")
    progress_bar.pack(pady=10)

    # Aggiungi la barra di progresso e la label alla finestra di dialogo
    dialog.progress_bar = progress_bar
    dialog.progress_label = progress_label

    # Avvia l'aggiornamento in un thread separato
    thread = threading.Thread(target=update_prices_threaded, args=(dialog, update_all))
    thread.start()

    # La finestra di dialogo rimane aperta finché il thread non termina
    dialog.wait_window()


def view_graph_for_product(product_name):
    """
    Visualizza un grafico dei prezzi per un prodotto specifico.
    
    Args:
        product_name (str): Il nome del prodotto di cui visualizzare il grafico.
    """
    def create_graph_for_product(product_name):
        """
        Crea un grafico dei prezzi per un prodotto specifico.
        
        Args:
            product_name (str): Il nome del prodotto di cui creare il grafico.
        
        Returns:
            fig (plotly.graph_objects.Figure): Il grafico creato.
        """
        # Verifica se il prodotto esiste nei dati
        if product_name not in prices:
            raise ValueError(f"Prodotto '{product_name}' non trovato in prices")

        # Prepara il DataFrame per il prodotto specificato
        df = pd.DataFrame(prices[product_name])
        df['date'] = pd.to_datetime(df['date'])

        # Crea una figura
        fig = go.Figure()

        # Aggiungi la traccia per il prodotto specificato
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['price'],
            mode='lines+markers',
            name=product_name,
            hovertemplate='Date: %{x}<br>Price: %{y}<extra></extra>'
        ))

        # Aggiorna il layout della figura
        fig.update_layout(
            title=f'Prezzi del Prodotto: {product_name}',
            xaxis_title='Data',
            yaxis_title='Prezzo',
            xaxis=dict(type='date'),
            hovermode='x'
        )
        
        return fig

    global panel_prices

    # Crea una nuova applicazione PyQt5 solo se non esiste già
    if panel_prices is None:
        panel_prices = QApplication([])

    # Crea la figura per il prodotto specificato
    fig = create_graph_for_product(product_name)
    
    # Salva la figura come stringa HTML
    html_str = pio.to_html(fig, full_html=True)
    
    # Crea un file HTML temporaneo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as temp_file:
        temp_file.write(html_str.encode('utf-8'))
        temp_file.flush()
        temp_file_path = temp_file.name

    # Crea una finestra principale
    qMainWindow = QMainWindow()
    qMainWindow.setWindowTitle(f'Grafico Prezzi - {product_name}')

    # Crea un widget centrale e un layout
    central_widget = QWidget()
    qVBoxLayout = QVBoxLayout(central_widget)
    qMainWindow.setCentralWidget(central_widget)

    # Crea un QWebEngineView e carica il file HTML temporaneo
    web_view = QWebEngineView()
    web_view.setUrl(QUrl.fromLocalFile(temp_file_path))
    qVBoxLayout.addWidget(web_view)

    # Mostra la finestra
    qMainWindow.resize(800, 600)
    qMainWindow.show()

    # Avvia l'applicazione se non è già in esecuzione
    panel_prices.exec_()

    # Pulisci il file temporaneo
    os.remove(temp_file_path)


def sort_by_column(col_idx):
    """
    Ordina i prodotti visualizzati in base alla colonna selezionata.
    
    Args:
        col_idx (int): L'indice della colonna su cui ordinare.
    """
    global products_to_view

    # Ottieni gli elementi della vista dei prodotti come una lista di tuple
    items = list(products_to_view.items())
    
    # Nome della colonna selezionata
    column_name = columns[col_idx]

    # Mappa i nomi delle colonne alle funzioni di ordinamento
    column_key_map = {
        'Nome': lambda item: item[0].lower(),
        'URL': lambda item: item[1]['url'].lower(),
        'Prezzo': lambda item: item[1]['price'] if isinstance(item[1]['price'], (int, float)) else float('inf'),
        'Notifica': lambda item: item[1]['notify'],
        'Timer': lambda item: (item[1]['timer'] + item[1]['timer_refresh']) - time.time(),
        'Timer Aggiornamento [s]': lambda item: item[1]['timer_refresh'],
        'Data Inserimento': lambda item: item[1]['date_added'],
        'Data Ultima Modifica': lambda item: item[1]['date_edited']
    }

    # Verifica se la colonna selezionata è quella precedentemente ordinata
    if sort_state['column'] == column_name:
        # Cambia l'ordine di ordinamento (cicla tra crescente, decrescente e nessun ordinamento)
        sort_state['order'] = (sort_state['order'] + 1) % 3
    else:
        # Imposta la nuova colonna e ordina in ordine crescente
        sort_state['column'] = column_name
        sort_state['order'] = 1  

    # Ordina gli elementi in base alla colonna selezionata e all'ordine
    if sort_state['order'] == 0:
        # Ripristina l'ordine iniziale
        items.sort(key=column_key_map['Data Ultima Modifica'])
        sort_state['column'] = None
    elif sort_state['order'] == 1:
        # Ordina in ordine crescente
        items.sort(key=column_key_map[column_name])
    else:
        # Ordina in ordine decrescente
        items.sort(key=column_key_map[column_name], reverse=True)

    # Aggiorna il dizionario con l'ordine ordinato
    products_to_view = {name: details for name, details in items}

    # Aggiorna l'intestazione della colonna per riflettere la direzione dell'ordinamento
    for column in columns:
        products_tree.heading(column, text=column, anchor='center')
    
    if sort_state['order'] != 0:
        # Aggiungi l'indicatore di ordinamento (▲ per crescente, ▼ per decrescente)
        sort_indicator = '▲' if sort_state['order'] == 1 else '▼'
        products_tree.heading(column_name, text=f"{column_name} {sort_indicator}", anchor='center')


def update_products_to_view():
    """
    Aggiorna la visualizzazione dei prodotti in base al testo di ricerca.
    Se il testo di ricerca è vuoto, mostra tutti i prodotti.
    """
    def filter_products(search_text):
        """
        Filtra i prodotti in base al testo di ricerca.
        
        Args:
            search_text (str): Il testo di ricerca per filtrare i prodotti.

        Returns:
            dict: Un dizionario di prodotti filtrati.
        """
        search_text = search_text.lower()
        filtered_products = {
            name: details
            for name, details in products.items()
            if search_text in name.lower()
        }
        return filtered_products

    global products_to_view

    # Resetta i filtri senza resettare la barra di ricerca
    reset_filters(reset_search_bar=False)

    # Ottieni il testo di ricerca dalla barra di ricerca
    search_text = search_entry.get()
    
    # Filtra i prodotti in base al testo di ricerca
    if search_text != "":
        products_to_view = filter_products(search_text)
    else:
        # Se non c'è testo di ricerca, mostra tutti i prodotti
        products_to_view = products


def show_product_details(event=None):
    """
    Mostra una finestra con i dettagli del prodotto selezionato, inclusi prezzo attuale,
    prezzi storici e suggerimenti basati sul prezzo.

    Args:
        event (tk.Event, opzionale): Evento che può scatenare la selezione. Non utilizzato in questa funzione.
    """
    def copy_to_clipboard(text, show_info=False):
        """
        Copia il testo negli appunti.
        """
        pyperclip.copy(text)
        if show_info:
            messagebox.showinfo("Copia negli appunti", "URL copiato negli appunti!")

    selected = products_tree.selection()

    if not selected:
        logger.warning("Nessun prodotto selezionato per visualizzare i dettagli")
        return
    
    if len(products_tree.selection()) > 1:
        logger.warning("Più di un prodotto selezionato per visualizzare i dettagli")
        return
    
    product_name = selected[0]

    # Estrazione dei dati
    url = products[product_name]['url']
    current_price = products[product_name]['price']
    historical_prices = prices.get(product_name, [])
    
    # Calcoli sui prezzi storici
    all_prices = [entry['price'] for entry in historical_prices if isinstance(entry['price'], (int, float))]
    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = current_price

    text_suggestion, color_suggestion = calculating_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)
    
    # Creazione della finestra dei dettagli
    details_window = tk.Toplevel(root)
    details_window.title(f"Dettagli del prodotto: {product_name}")
    details_window.minsize(500, 300)
    details_window.configure(padx=20, pady=10)  # Padding per la finestra
    details_window.transient(root)
    details_window.grab_set()

    # Configurazione del layout a griglia
    for i in range(5):
        details_window.grid_columnconfigure(i, weight=1)
    
    # Font per il nome del prodotto e per il prezzo corrente
    name_font = ('Helvetica', 12, 'bold')
    highlight_font = ('Helvetica', 14, 'bold')
    
    # Creazione di un frame per il nome del prodotto e il pulsante "Visualizza Grafico"
    top_frame = ttk.Frame(details_window)
    top_frame.pack(fill='x', pady=10)

    top_frame.grid_columnconfigure(0, weight=1)
    top_frame.grid_columnconfigure(1, weight=1)
    top_frame.grid_columnconfigure(2, weight=0)

    # Nome del prodotto
    name_label = ttk.Label(top_frame, text=product_name, font=name_font)
    name_label.grid(row=0, column=0, sticky='w')

    # Pulsante per visualizzare il grafico
    view_graph_button = ttk.Button(top_frame, text="Visualizza Grafico", command=lambda: view_graph_for_product(product_name))
    view_graph_button.grid(row=0, column=1, sticky='e')

    # URL del prodotto
    truncated_url = (url[:45] + '...') if len(url) > 45 else url
    url_label = ttk.Label(top_frame, text=truncated_url, font=common_font, foreground="blue", cursor="hand2")
    url_label.grid(row=1, column=0, sticky='w')
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    copy_image_label = ttk.Button(top_frame, text="Copia Url", command=lambda:copy_to_clipboard(url))
    copy_image_label.grid(row=1, column=1, sticky='e')

    # Frame per le informazioni sui prezzi
    prices_frame = ttk.Frame(details_window)
    prices_frame.pack(anchor="w", padx=10)

    # Prezzo corrente
    current_price_label = ttk.Label(prices_frame, text=f"Prezzo Attuale: {current_price:.2f}€" if isinstance(current_price, (int, float)) else "Prezzo Attuale: -", font=highlight_font, foreground=color_suggestion)
    current_price_label.grid(row=0, column=0, sticky='w', pady=(5, 10))

    # Prezzi storici
    ttk.Label(prices_frame, text="Prezzo Medio:", font=common_font).grid(row=1, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{average_price:.2f}€" if isinstance(average_price, (int, float)) else "-", font=common_font).grid(row=1, column=1, sticky='e', pady=5)

    ttk.Label(prices_frame, text="Prezzo Minimo Storico:", font=common_font).grid(row=2, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{price_minimum:.2f}€" if isinstance(price_minimum, (int, float)) else "-", font=common_font).grid(row=2, column=1, sticky='e', pady=5)

    ttk.Label(prices_frame, text="Prezzo Massimo Storico:", font=common_font).grid(row=3, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{price_maximum:.2f}€" if isinstance(price_maximum, (int, float)) else "-", font=common_font).grid(row=3, column=1, sticky='e', pady=5)
    
    # Suggerimento basato sui prezzi
    suggerimento_label = ttk.Label(details_window, text=text_suggestion, font=name_font, foreground=color_suggestion)
    suggerimento_label.pack(pady=10)
    
    # Pulsante per chiudere la finestra
    ttk.Button(details_window, text="Chiudi", command=details_window.destroy).pack(pady=10)
    details_window.update_idletasks()


def show_context_menu(event):
    """
    Mostra un menu contestuale quando si fa clic con il tasto destro su un elemento nella TreeView.
    Il menu visualizzato dipende se è selezionato uno o più elementi.
    
    Args:
        event (tk.Event): Evento del mouse che contiene informazioni sul clic.
    """
    # Ottieni le coordinate del click
    x, y = event.x, event.y
    
    # Ottieni l'ID dell'elemento sotto il puntatore del mouse
    item = products_tree.identify_row(y)
    
    # Se c'è un elemento sotto il puntatore
    if item:
        # Se l'elemento non è selezionato, selezionalo
        if not products_tree.selection() or item not in products_tree.selection():
            products_tree.selection_set(item)
            products_tree.focus(item)

    # Ottieni gli elementi selezionati
    selected_items = products_tree.selection()
    
    # Mostra il menu contestuale appropriato
    if len(selected_items) > 1:
        multi_selection_menu.post(event.x_root, event.y_root)
    elif len(selected_items) == 1:
        single_selection_menu.post(event.x_root, event.y_root)


def click_products(event):
    global current_index

    item_id = products_tree.identify_row(event.y)
    items = products_tree.get_children()

    if item_id in items:
        current_index = items.index(item_id)
        if not event.state & 0x0004:  # Se Ctrl NON è premuto
            # Rimuovi la selezione corrente e seleziona solo l'elemento cliccato
            products_tree.selection_remove(*products_tree.selection())
            products_tree.selection_add(items[current_index])
        else:  # Se Ctrl è premuto
            # Verifica se l'elemento è già selezionato (toggle)
            if items[current_index] in products_tree.selection():
                products_tree.selection_remove(items[current_index])  # Deseleziona se è selezionato
            else:
                products_tree.selection_add(items[current_index])  # Seleziona se non è selezionato


def shift_click_products(event):
    global current_index

    products_tree.selection_remove(*products_tree.selection())

    # Ottieni l'item cliccato
    item_id = products_tree.identify_row(event.y)
    items = products_tree.get_children()

    # Se l'item_id è vuoto, esci dalla funzione
    if not item_id:
        return

    # Se current_index è None, parti dal primo elemento (index 0)
    if current_index is None:
        current_index = 0

    # Trova l'indice dell'elemento cliccato
    clicked_index = items.index(item_id)

    # Trova il range tra current_index e clicked_index
    start = min(current_index, clicked_index)
    end = max(current_index, clicked_index)

    # Seleziona tutti gli elementi tra current_index e l'elemento cliccato
    for i in range(start, end + 1):
        products_tree.selection_add(items[i])


def navigate_products(event):
    """
    Naviga tra gli elementi della TreeView usando le frecce su e giù.
    Seleziona il prossimo o il precedente elemento in base alla direzione della freccia.
    
    Args:
        event (tk.Event): Evento della tastiera che indica quale tasto è stato premuto.
    """
    global current_index

    selected_items = products_tree.selection()

    if not selected_items:
        return
    
    items = products_tree.get_children()

    # Ottieni l'indice di ogni elemento selezionato
    selected_indices = [products_tree.index(item) for item in selected_items]
    selected_indices.sort()
    is_consecutive = True
    # Controlla se sono consecutivi
    for i in range(1, len(selected_indices)):
        if selected_indices[i] != selected_indices[i - 1] + 1 or current_index not in selected_indices:
            products_tree.selection_remove(selected_items)
            if current_index is None:
                current_index = products_tree.index(selected_items[0])
            products_tree.selection_add(items[current_index])
            selected_items = products_tree.selection()
            is_consecutive = False
            break

    if is_consecutive and current_index is None:
        current_index = products_tree.index(selected_items[0])

    temp_index = current_index

    if event.keysym == 'Down':
        # Se la freccia giù è premuta, vai al prossimo elemento
        next_index = current_index = min(current_index + 1, len(items) - 1)
    elif event.keysym == 'Up':
        # Se la freccia su è premuta, vai all'elemento precedente
        next_index = current_index = max(current_index - 1, 0)
    else:
        return
    
    if event.state & 0x0001: # Tasto shift premuto
        if items[next_index] in selected_items:
            if (next_index != 0 and next_index != len(items) - 1):
                products_tree.selection_remove(items[temp_index])
        else:
            products_tree.selection_add(items[next_index])
    else:
        # Se il tasto Shift non è premuto, aggiorna la selezione
        products_tree.selection_remove(selected_items)
        products_tree.selection_add(items[next_index])

    products_tree.see(items[next_index])


def select_all_products(event=None):
    """
    Seleziona tutti gli elementi nella TreeView.
    
    Args:
        event (tk.Event, opzionale): Evento che può scatenare la selezione. Non utilizzato in questa funzione.
    """
    global current_index

    products_tree.selection_set(products_tree.get_children())
    current_index = None


def clear_selected_products(event=None):
    """
    Deseleziona tutti gli elementi nella TreeView se il clic è avvenuto in un'area vuota.
    Se il clic è avvenuto su una riga, non fa nulla.
    
    Args:
        event (tk.Event, opzionale): Evento del mouse che può indicare la posizione del clic.
    """
    global current_index

    # Identifica la riga sotto il puntatore del mouse
    row_id = products_tree.identify_row(event.y)

    if not row_id:
        # Se il clic è avvenuto in un'area vuota della TreeView, deseleziona tutti gli elementi
        if event.widget == products_tree:
            products_tree.selection_remove(*products_tree.selection())
            current_index = None


def periodic_update():
    """
    Esegue aggiornamenti periodici sulla TreeView e sui pulsanti.
    Ricarica i dati nella TreeView e aggiorna lo stato dei pulsanti. 
    Viene chiamata ogni 500 millisecondi per mantenere l'interfaccia aggiornata.
    """
    def refresh_treeview():
        """
        Ricarica i dati nella TreeView con i prodotti da visualizzare.
        Aggiorna anche il timer di aggiornamento per ogni prodotto.
        """
        def calculate_time_remaining(last_checked_time, update_interval):
            """
            Calcola il tempo rimanente fino al prossimo aggiornamento previsto.
            
            Args:
                last_checked_time (float): Timestamp dell'ultimo aggiornamento.
                update_interval (float): Intervallo di aggiornamento in secondi.
            
            Returns:
                str: Tempo rimanente formattato come "Xh Ym Zs".
            """
            next_check = last_checked_time + update_interval
            time_remaining = next_check - time.time()
            if time_remaining < 0:
                time_remaining = 0

            hours, remainder = divmod(time_remaining, 3600)
            minutes, seconds = divmod(remainder, 60)

            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        # Salva la selezione corrente
        selection = products_tree.selection()
        # Pulisce la TreeView
        products_tree.delete(*products_tree.get_children())

        # Inserisce i nuovi dati nella TreeView
        for name in products_to_view:
            timer_text = calculate_time_remaining(products_to_view[name]['timer'], products_to_view[name]['timer_refresh'])
            products_tree.insert("", "end", iid=name, values=(
                name,
                products_to_view[name]['url'],
                f"{str(products_to_view[name]['price'])}€",
                "Si" if products_to_view[name]['notify'] else "No",
                timer_text,
                products_to_view[name]['timer_refresh'],
                products_to_view[name]['date_added'],
                products_to_view[name]['date_edited']
            ))

        # Ripristina la selezione
        for item_id in selection:
            if item_id in products_tree.get_children():
                products_tree.selection_add(item_id)

    def update_buttons_state():
        """
        Aggiorna lo stato dei pulsanti in base agli elementi selezionati nella TreeView.
        I pulsanti vengono abilitati o disabilitati a seconda se ci sono selezioni multiple,
        una singola selezione o nessuna selezione. 
        """
        selected_items = products_tree.selection()
        num_selected = len(selected_items)

        if num_selected > 1:
            # Se ci sono più di un elemento selezionato
            remove_button['state'] = "normal"
            update_button['state'] = "normal"
            add_button['state'] = "normal"  # Mantieni attivo anche add_button
            update_all_button['state'] = "normal" if products_to_view else "disabled"

            edit_button['state'] = "disabled"
            view_button['state'] = "disabled"
        elif num_selected == 1:
            # Se c'è un solo elemento selezionato
            remove_button['state'] = "normal"
            update_button['state'] = "normal"
            edit_button['state'] = "normal"
            view_button['state'] = "normal"

            add_button['state'] = "normal"
            update_all_button['state'] = "normal" if products_to_view else "disabled"
        else:
            # Se non ci sono elementi selezionati
            remove_button['state'] = "disabled"
            update_button['state'] = "disabled"
            edit_button['state'] = "disabled"
            view_button['state'] = "disabled"

            add_button['state'] = "normal"
            update_all_button['state'] = "normal" if products_to_view else "disabled"

    if enable_update:
        refresh_treeview()

        update_buttons_state()

        # Richiama periodicamente questa funzione
        root.after(500, periodic_update)  # Ogni 500 millisecondi


def set_enable_update(update = True):
    def disable_controls():
        add_button.config(state="disabled")
        view_button.config(state="disabled")
        edit_button.config(state="disabled")
        remove_button.config(state="disabled")
        update_button.config(state="disabled")
        update_all_button.config(state="disabled")
        search_entry.config(state="disabled")

    def enable_controls():
        add_button.config(state="normal")
        view_button.config(state="normal")
        edit_button.config(state="normal")
        remove_button.config(state="normal")
        update_button.config(state="normal")
        update_all_button.config(state="normal")
        search_entry.config(state="normal")

    global enable_update

    if update:
        enable_controls()
        enable_update = True

        for name in products:
            start_tracking(name, products[name]['url'])

        periodic_update()
        enable_controls()
    else:
        disable_controls()
        enable_update = False

        for name in products:
            stop_events[name].set() # Segnala al thread corrente di fermarsi
            threads[name].join(timeout=1) # Aspetta che il thread corrente termini


# Configurazioni
columns = ("Nome", "URL", "Prezzo", "Notifica", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica")

products_file = "products.json"
products = {}
products_to_view = {}

prices_file = 'prices.json'
prices = {}
panel_prices = None

threads = {}
stop_events = {}

sort_state = {
    'column': None,
    'order': 0  # 0: nessun ordinamento, 1: crescente, 2: decrescente
}

common_font = ('Arial', 10)

current_index = None

enable_update = True

# Creazione della finestra principale
root = tk.Tk()
root.title("Monitoraggio Prezzi Amazon")
root.minsize(1300, 300)
root.wm_state("zoomed")

# Limita la lunghezza dell'input
limit_letters = (root.register(lambda s: len(s) <= 50), '%P')

# Frame per l'input dell'utente
input_frame = ttk.Frame(root)
input_frame.pack(fill="x", padx=10, pady=(15, 0))

# Bottone Aggiungi
add_button = ttk.Button(input_frame, text="Aggiungi", command=open_add_product_dialog)
add_button.grid(row=2, column=0, padx=5, pady=5, sticky="we")

# Bottone Visualizza
view_button = ttk.Button(input_frame, text="Visualizza", command=show_product_details, state="disabled")
view_button.grid(row=2, column=1, padx=5, pady=5, sticky="we")

# Bottone Modifica
edit_button = ttk.Button(input_frame, text="Modifica", command=open_edit_product_dialog, state="disabled")
edit_button.grid(row=2, column=2, padx=5, pady=5, sticky="we")

# Bottone Rimuovi
remove_button = ttk.Button(input_frame, text="Rimuovi", command=remove_products, state="disabled")
remove_button.grid(row=2, column=3, padx=5, pady=5, sticky="we")

# Colonna vuota per separare i bottoni
ttk.Label(input_frame, text="", width=18).grid(row=2, column=4, padx=5, pady=5, sticky="we")

# Bottone Aggiorna Selezionati
update_button = ttk.Button(input_frame, text="Aggiorna Selezionati", command=lambda:open_progress_dialog(False), state="disabled")
update_button.grid(row=2, column=5, padx=5, pady=5, sticky="e")

# Bottone Aggiorna Tutti
update_all_button = ttk.Button(input_frame, text="Aggiorna Tutti", command=lambda:open_progress_dialog(), state="disabled")
update_all_button.grid(row=2, column=6, padx=5, pady=5, sticky="e")

# Setup della barra di ricerca
search_frame = ttk.Frame(root)
search_frame.pack(fill="x", padx=5, pady=0)

ttk.Label(search_frame, text="Ricerca Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
search_entry = ttk.Entry(search_frame, width=80, font=common_font, validate='key', validatecommand=limit_letters)
search_entry.grid(row=0, column=1, padx=10, pady=10, sticky='we')
search_entry.update_idletasks()
search_entry.bind("<KeyRelease>", lambda event: update_products_to_view())
search_entry.bind("<Button-3>", lambda e: show_text_menu(e, search_entry))

# Tabella dei prodotti
frame_products_tree = tk.Frame(root)
frame_products_tree.pack(fill="both", expand=True, padx=(15, 10), pady=(10, 0))
products_tree = ttk.Treeview(frame_products_tree, columns=columns, show="headings", selectmode="none")
# Configurazione delle colonne della TreeView
for idx, col in enumerate(columns):
    products_tree.heading(col, text=col, anchor='center', command=lambda _idx=idx: sort_by_column(_idx))
    products_tree.column(col, width=80 if col in ['Notifica'] else 200, anchor='center' if col in ['Prezzo', 'Notifica', 'Timer', 'Timer Aggiornamento [s]', 'Data Inserimento', 'Data Ultima Modifica'] else 'w')
# Scrollbar
scrollbar = ttk.Scrollbar(frame_products_tree, orient="vertical", command=products_tree.yview)
products_tree.configure(yscrollcommand=scrollbar.set)
products_tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Frame per la barra di progresso e la label
frame_footer = tk.Frame(root)
frame_footer.pack(side="bottom", fill="x", padx=(20, 40), pady=2)

creator_label = tk.Label(frame_footer, text="Prodotto da Vincenzo Salvati", font=("Arial", 8))
creator_label.pack(side="right")

# Menu contestuale per la singola selezione
single_selection_menu = tk.Menu(root, tearoff=0)
single_selection_menu.add_command(label="Visualizza prodotto", command=show_product_details)
single_selection_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog)
single_selection_menu.add_command(label="Rimuovi prodotto", command=remove_products)

# Menu contestuale per selezione multipla
multi_selection_menu = tk.Menu(root, tearoff=0)
multi_selection_menu.add_command(label="Rimuovi selezionati", command=remove_products)
multi_selection_menu.add_command(label="Aggiorna selezionati", command=lambda:open_progress_dialog(False))

# Binding degli eventi
products_tree.bind("<Double-1>", show_product_details)
products_tree.bind("<Return>", show_product_details)
products_tree.bind("<Button-3>", show_context_menu)
products_tree.bind("<Button-1>", click_products)
products_tree.bind("<Shift-Button-1>", shift_click_products)
products_tree.bind("<Down>", navigate_products)
products_tree.bind("<Up>", navigate_products)

root.bind("<Control-a>", select_all_products)
root.bind("<Button-1>", clear_selected_products)

# Carica dati
load_data()
load_prices_data()

# Reset dei timer
for name in products:
    products[name]['timer'] = time.time()
save_data()

# Avvia l'aggiornamento periodico
periodic_update()

# Avvia il main loop dell'interfaccia grafica
root.mainloop()
