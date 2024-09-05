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
        config_file = "config.json"

        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as file:
                    config = json.load(file)

                    return (config["sender_email"], config["sender_password"], config["receiver_email"], config["url_telegram"], config["chat_id_telegram"])
        
            except Exception as e:
                logger.error(f"Errore nel caricamento del file di configurazione: {e}")

                messagebox.showerror("Attenzione", f"Errore nel caricamento del file di configurazione")

                exit()
        else:
            logger.error(f"File di configurazione '{config_file}' non trovato")

            messagebox.showerror("Attenzione", f"File di configurazione '{config_file}' non trovato")
            
            exit()


def send_email(subject, body, email_to_notify):
    from_email, from_password, _, _, _ = load_config()

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = email_to_notify
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com:587")
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, email_to_notify, text)
        server.quit()
    except Exception as e:
        logger.error(f"Impossibile inviare l'email: {e}")


def send_notification(subject, body):
    
    _, _, recipient_email, url_telegram, chat_id_telegram = load_config()

    # Invio email
    send_email(subject, body, recipient_email)

    # Invio Telegram
    try:
        payload = {"chat_id": chat_id_telegram, "text": ""}
        payload["text"] = body
        response = requests.post(url_telegram, data=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Impossibile inviare il messaggio Telegram: {e}")


def reset_filters(reset_search_bar=True):
    global products_to_view, sort_state, products_tree, search_entry

    sort_state = {
    'column': None,
    'order': 0
    }

    items = list(products_to_view.items())
    column_key_map = {
        'Nome': lambda item: item[0].lower(),
        'URL': lambda item: item[1]['url'].lower(),
        'Prezzo': lambda item: item[1]['price'] if isinstance(item[1]['price'], (int, float)) else float('inf'),
        'Timer': lambda item: item[1]['timer'],
        'Timer Aggiornamento [s]': lambda item: item[1]['timer_refresh'],
        'Data Inserimento': lambda item: item[1]['date_added'],
        'Data Ultima Modifica': lambda item: item[1]['date_edited']
    }
    items.sort(key=column_key_map["Data Ultima Modifica"])

    products_to_view = {name: details for name, details in items}

    for column in columns:
        products_tree.heading(column, text=column, anchor='center')

    if reset_search_bar:
        search_entry.delete(0, tk.END)


def get_price(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Trovare il titolo del prodotto
        title_element = soup.find("span", id="productTitle")
        
        if title_element is None:
            raise ValueError("Titolo del prodotto non trovato")

        # Il parent container del titolo
        title_container = title_element.find_parent()

        # Cercare l'elemento di prezzo immediatamente dopo il titolo
        price_element = title_container.find_next("span", class_="aok-offscreen")

        if price_element is None:
            raise ValueError("Elemento prezzo non trovato sotto il titolo")

        price_text = price_element.get_text().strip()

        match = re.search(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})?', price_text)
        if match:
            price_value = match.group(0).replace(".", "").replace(",", ".")
            
            return float(price_value)
        else:
            raise ValueError("Prezzo non trovato nel testo")

    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP di getPrice: {e}")
        return None
    except Exception as e:
        logger.error(f"Errore in getPrice: {e}")
        return None


def get_last_price(name):
    global prices

    if name in prices:
        last_entry = max(prices[name], key=lambda x: x["date"])

        return last_entry["price"]
    else:
        return None


def start_tracking(name, url):
    def track_loop(name, url):
        def check_price_and_notify(name, url):
            current_price = get_price(url)

            if current_price is None:
                logger.warning(f"Non trovato il prezzo di {name} sulla pagina {url}")
                return

            previous_price = products[name]["price"] if isinstance(products[name]["price"], (int, float)) else get_last_price(name)
            
            subject="Prezzo in calo!"
            body=f"Il prezzo dell'articolo {name} è sceso da {previous_price}€ a {current_price}€\nAcquista ora: {products[name]['url']}"
            
            if previous_price is None:
                logger.warning(f"Non trovato il prezzo di {name} nelle liste")
                return

            if current_price < previous_price:
                send_notification(subject=subject, body=body)
            
            for key, value in products[name]["emails_and_thresholds"].items():
                value_to_compare = previous_price
                subject_to_send = subject
                body_to_send = body

                if value != 0.0:
                    value_to_compare = value
                    subject_to_send="Prezzo inferiore alla soglia indicata!"
                    body_to_send=f"Il prezzo dell'articolo {name} è al di sotto della soglia di {value_to_compare}€ indicata.\nIl costo è {current_price}€\nAcquista ora: {products[name]['url']}"              
                
                if current_price < value_to_compare:
                    send_email(subject=subject_to_send, body=body_to_send, email_to_notify = key)

            products[name]["price"] = current_price

            save_prices_data(name, products[name]["price"])

            save_data()

        global products, stop_flags

        while not stop_flags.get(name, False):
            time.sleep(products[name]["timer_refresh"])

            check_price_and_notify(name, url)

            products[name]["timer"] = time.time()

            reset_filters()

    global stop_flags, threads

    stop_flags[name] = False
    timer_thread = threading.Thread(target=track_loop, args=(name, url,), daemon=True,)
    threads[name] = timer_thread
    timer_thread.start()

    logger.info(f"Avviato il monitoraggio per '{name}' ({url})")


def load_data():
    global products_file, products, products_to_view

    if os.path.exists(products_file):
        try:
            with open(products_file, "r") as file:
                products = json.load(file)

                for name in products:
                    if not isinstance(products[name], dict):
                        raise Exception("Ogni elemento nel file JSON dei dati articoli deve essere un dizionario")

                    url = products[name]["url"]

                    if not url:
                        raise Exception("Ogni prodotto deve avere un 'url'")

                    start_tracking(name, url)

                products_to_view = products

                logger.info("Dati dei prodotti caricati correttamente")

        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati articoli: {e}")

            messagebox.showerror("Attenzione", f"Errore durante il caricamento dei dati articoli")

            exit()
    else:
        logger.warning(f"File dei dati articoli '{products_file}' non trovato")

        messagebox.showwarning("Attenzione", f"File dei dati articoli '{products_file}' non trovato")


def save_data():
    try:
        global products_file, products, products_to_view

        with open(products_file, "w") as file:
            json.dump(products, file, indent=4)

        products_to_view = products

        logger.info("Dati articoli salvati con successo")

    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati articoli: {e}")


def load_prices_data():
    global prices_file, prices

    if os.path.exists(prices_file):
        try:
            with open(prices_file, "r") as file:
                prices = json.load(file)

                for name in prices:
                    if not isinstance(prices[name], list):
                        raise Exception("Ogni elemento nel file JSON dei dati monitoraggio prezzi deve essere una lista")

                logger.info("Dati monitoraggio prezzi caricati correttamente")

        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati monitoraggio prezzi: {e}")

            messagebox.showerror("Attenzione", f"Errore durante il caricamento dei dati monitoraggio prezzi")

            exit()
    else:
        logger.warning(f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")

        messagebox.showwarning("Attenzione", f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")


def save_prices_data(name, price):
    global prices_file, prices

    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
    window.update_idletasks()  # Aggiorna le dimensioni della finestra
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')


def open_add_product_dialog():
    def on_entry_focus_in(event):
        # Mostra la Listbox quando l'Entry riceve il focus
        update_suggestions()

    def on_entry_focus_out(event):
        # Nascondi la Listbox quando l'Entry perde il focus
        listbox_suggestions.place_forget()

    def update_suggestions(*args):
        global prices

        typed_text = name_entry_var.get().strip().lower()
        listbox_suggestions.delete(0, tk.END)
        
        if typed_text:
            matching_suggestions = [name for name in prices.keys() if typed_text in name.lower()]
            
            for suggestion in matching_suggestions:
                listbox_suggestions.insert(tk.END, suggestion)

            if matching_suggestions:
                listbox_suggestions.config(height=min(len(matching_suggestions), 5))

                # Posizionare la listbox sotto l'entry
                x = name_entry.winfo_x()
                y = name_entry.winfo_y() + name_entry.winfo_height()
                listbox_suggestions.place(x=x, y=y, anchor="nw")
                listbox_suggestions.lift()  # Assicurati che la listbox sia sopra gli altri widget
            else:
                listbox_suggestions.place_forget()
        else:
            listbox_suggestions.place_forget()

    def on_select_suggestion(event):
        selection = listbox_suggestions.curselection()
        if selection:  # Verifica se c'è una selezione
            selected_name = listbox_suggestions.get(selection[0])
            name_entry.delete(0, tk.END)
            name_entry.insert(0, selected_name)
            listbox_suggestions.place_forget()


    def on_add_product(name, url):
        def add_product(name, url):
            global products

            if not name or not url:
                messagebox.showwarning("Attenzione", "Compila tutti i campi!")
                return False

            for product_name in products:
                if name == product_name:
                    messagebox.showwarning("Attenzione", "Il nome del prodotto è già presente!\nCambia il nome")
                    return False

                if url == products[product_name]["url"]:
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
                "timer": time.time(),
                "timer_refresh": timer_refresh,
                "date_added": now,
                "date_edited": now,
                "emails_and_thresholds": emails_and_thresholds  # Inserisce le email e soglie
            }
            
            save_data()
            save_prices_data(name, products[name]["price"]) 
            start_tracking(name, url)
            reset_filters()

            return True

        if add_product(name, url):
            add_product_dialog.destroy()

    def open_advanced_dialog():
        def add_email_threshold():
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
            table.delete(*table.get_children())
            for key, value in sorted(emails_and_thresholds.items()):
                table.insert("", "end", iid=key, values=(key, str(value)+"€"))

        def show_context_menu(event):
            item = table.identify_row(event.y)
            if not item:
                return
            table.selection_set(item)
            context_menu.post(event.x_root, event.y_root)

        def remove_email():
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            del emails_and_thresholds[email]
            update_table()

        def modify_threshold():
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
            return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

        def on_timer_change(*args):
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

        advanced_dialog = tk.Toplevel(root)
        advanced_dialog.title("Aggiungi e-mail e soglia notifica")
        advanced_dialog.resizable(False, False)

        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(lambda s: s.isdigit() or s in ['.', '-']), '%S'))
        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        # Tabella per mostrare email e soglie aggiunte
        columns = ("Email", "Soglia")
        global table
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

        # Associa la funzione di callback per aggiornare il valore del timer
        timer_entry.bind('<KeyRelease>', on_timer_change)

        advanced_dialog.transient(root)
        advanced_dialog.grab_set()
        center_window(advanced_dialog)

    global root, common_font, limit_letters, emails_and_thresholds, timer_refresh

    emails_and_thresholds = {}
    timer_refresh = 1800

    add_product_dialog = tk.Toplevel(root)
    add_product_dialog.title("Aggiungi Prodotto")
    add_product_dialog.resizable(False, False)

    container = ttk.Frame(add_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    name_entry_var = tk.StringVar()
    name_entry_var.trace('w', update_suggestions)

    name_entry = ttk.Entry(container, width=80, font=common_font, textvariable=name_entry_var, validate='key', validatecommand=limit_letters)
    name_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')

    # Listbox per suggerimenti
    listbox_suggestions = tk.Listbox(add_product_dialog, width=80)  # Altezza verrà configurata dinamicamente
    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)
    listbox_suggestions.place_forget()  # Inizialmente nascosta

    # Associa eventi di movimento del mouse
    name_entry.bind("<FocusIn>", on_entry_focus_in)
    name_entry.bind("<FocusOut>", on_entry_focus_out)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    # Crea un frame per ospitare il widget Text e la scrollbar
    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    # Crea il widget Text
    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)

    # Crea la scrollbar
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")

    # Configura il widget Text per usare la scrollbar
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Button(container, text="Avanzate", command=lambda: open_advanced_dialog()).grid(row=2, column=0, pady=10, sticky="w")

    ttk.Button(container, text="Aggiungi", command=lambda: on_add_product(name_entry.get().strip().lower(), url_text.get("1.0", "end-1c").strip())).grid(row=2, column=1, pady=10, sticky="e")

    add_product_dialog.transient(root)
    add_product_dialog.grab_set()
    center_window(add_product_dialog)


def open_edit_product_dialog():
    def on_edit_product(name, current_url, new_url):
        def edit_product(name, current_url, new_url):
            global products

            if not new_url:
                messagebox.showwarning("Attenzione", "Compila url!")
                return False

            if current_url != new_url:
                for product_name in products:
                    if new_url == products[product_name]["url"]:
                        messagebox.showwarning("Attenzione", "Questo articolo è già in monitoraggio!\nCambia url")
                        return False

            new_price = get_price(new_url)

            if new_price is None:                
                products[name]["price"] = "Aggiorna o verifica url: - "

                messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica url")

                logger.warning(f"Sul prodotto {name} non è stato trovato il prezzo sulla pagina " + products[name]["url"])
            else:
                products[name]["price"] = new_price

            products[name]["url"] = new_url
            products[name]["timer"] = time.time()
            products[name]["timer_refresh"] = timer_refresh
            products[name]["date_edited"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            products[name]["emails_and_thresholds"] = emails_and_thresholds

            save_data()
            save_prices_data(name, products[name]["price"])

            reset_filters()

            logger.info(f"Prodotto '{name}' modificato con successo")

            return True

        if edit_product(name, current_url, new_url):
            edit_product_dialog.destroy()

    def open_advanced_dialog():
        def add_email_threshold():
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
            table.delete(*table.get_children())
            for key, value in sorted(emails_and_thresholds.items()):
                table.insert("", "end", iid=key, values=(key, str(value)+"€"))

        def show_context_menu(event):
            item = table.identify_row(event.y)
            if not item:
                return
            table.selection_set(item)
            context_menu.post(event.x_root, event.y_root)

        def remove_email():
            selected = table.selection()
            if not selected:
                return
            email = selected[0]
            del emails_and_thresholds[email]
            update_table()

        def modify_threshold():
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
            return (input_value.isdigit() and int(input_value) >= 0) or input_value == ""

        def on_timer_change(*args):
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

        advanced_dialog = tk.Toplevel(root)
        advanced_dialog.title("Aggiungi e-mail e soglia notifica")
        advanced_dialog.resizable(False, False)

        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate='key', validatecommand=(root.register(lambda s: s.isdigit() or s in ['.', '-']), '%S'))
        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        # Tabella per mostrare email e soglie aggiunte
        columns = ("Email", "Soglia")
        global table
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

        update_table()

        advanced_dialog.transient(root)
        advanced_dialog.grab_set()
        center_window(advanced_dialog)

    global root, common_font, products_tree, emails_and_thresholds, timer_refresh

    selected_item = products_tree.selection()[0]
    selected_name = products_tree.item(selected_item)["values"][0]
    selected_url = products[selected_name]["url"]
    emails_and_thresholds = products[selected_name]["emails_and_thresholds"]
    timer_refresh = products[selected_name]["timer_refresh"]

    edit_product_dialog = tk.Toplevel(root)
    edit_product_dialog.title("Modifica Prodotto")
    edit_product_dialog.resizable(False, False)

    container = ttk.Frame(edit_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
    # Creazione di un tk.Text per il testo selezionabile
    text_widget = tk.Text(container, font=common_font, height=1, width=len(selected_name), wrap='none', bd=0, bg='white')
    text_widget.insert(tk.END, selected_name)
    text_widget.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    # Rendere il testo solo in lettura
    text_widget.config(state=tk.DISABLED)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")
    # Crea un frame per ospitare il widget Text e la scrollbar
    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")
    # Crea il widget Text
    url_text = tk.Text(text_frame, height=5, width=80)
    url_text.pack(side="left", fill="both", expand=True)
    url_text.insert("1.0", selected_url)
    # Crea la scrollbar
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    # Configura il widget Text per usare la scrollbar
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Button(container, text="Avanzate", command=lambda: open_advanced_dialog()).grid(row=2, column=0, pady=10, sticky="w")

    ttk.Button(container, text="Salva", command=lambda: on_edit_product(selected_name, selected_url, url_text.get("1.0", "end-1c").strip())).grid(row=2, column=1, pady=10, sticky="e")

    edit_product_dialog.transient(root)
    edit_product_dialog.grab_set()
    center_window(edit_product_dialog)


def remove_product():
    def stop_tracking(name):
        global stop_flags, threads

        stop_flags[name] = True

        if name in threads:
            threads[name].join(timeout=1)
            del threads[name]

        del stop_flags[name]

    global products, products_tree

    reset_filters()

    selected = products_tree.selection()

    if not selected:
        logger.warning("Seleziona un prodotto dalla lista per rimuoverlo")
        return

    for name in selected:
        del products[name]

        save_data()
        stop_tracking(name)

        logger.info(f"Prodotto '{name}' rimosso con successo")


def notify(name, prev_price, curr_price):
    global products

    subject="Prezzo in calo!"
    body=f"Il prezzo dell'articolo {name} è sceso da {prev_price}€ a {curr_price}€\nAcquista ora: {products[name]['url']}"

    send_notification(subject=subject, body=body)

    for key, value in products[name]["emails_and_thresholds"].items():
        value_to_compare = prev_price
        subject_to_send = subject
        body_to_send = body

        if value != 0.0:
            value_to_compare = value
            subject_to_send="Prezzo inferiore alla soglia indicata!"
            body_to_send=f"Il prezzo dell'articolo {name} è al di sotto della soglia di {value_to_compare}€ indicata.\nIl costo è {curr_price}€\nAcquista ora: {products[name]['url']}"              
        
        if curr_price < value_to_compare:
            send_email(subject=subject_to_send, body=body_to_send, email_to_notify = key)


def update_selected_prices():
    global products, products_tree

    reset_filters()

    selected = products_tree.selection()

    if not selected:
        logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
        return

    updated_products = []
    for item in selected:
        name = item
        current_price = get_price(products[name]["url"])

        if current_price is None:
            logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina " + products[name]["url"])

            products[name]["price"] = "Aggiorna o verifica url: - "
            products[name]["timer"] = time.time()
            products[name]["date_edited"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            continue

        products[name]["price"] = current_price
        products[name]["timer"] = time.time()
        products[name]["date_edited"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        previous_price = get_last_price(name)

        if previous_price is not None:
            updated_products.append((name, previous_price, current_price))

        save_prices_data(name, products[name]["price"])

    save_data()

    if updated_products:
        status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

        for name, prev_price, curr_price in updated_products:
            if curr_price < prev_price:
                status_message += f"{name}: Prezzo calato da {prev_price}€ a {curr_price}€\n"
                
                notify(name, prev_price, curr_price)
            elif curr_price > prev_price:
                status_message += f"{name}: Prezzo aumentato da {prev_price}€ a {curr_price}€\n"
            else:
                status_message += f"{name}: Prezzo invariato a {curr_price}€\n"

        messagebox.showinfo("Aggiornamento", status_message)

        logger.info("I prodotti selezionati sono stati aggiornati")
    else:
        messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali nuovamente")

        logger.warning("Nessun prodotto selezionato è stato aggiornato")


def update_all_prices():
    global products

    reset_filters()

    updated_products = []
    for name in products:
        current_price = get_price(products[name]["url"])
        
        if current_price is None:
            logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina " + products[name]["url"])

            products[name]["price"] = "Aggiorna o verifica url: - "
            products[name]["timer"] = time.time()
            products[name]["date_edited"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            continue

        products[name]["price"] = current_price
        products[name]["timer"] = time.time()
        products[name]["date_edited"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        previous_price = get_last_price(name)

        if previous_price is not None:
            updated_products.append((name, previous_price, current_price))

        save_prices_data(name, products[name]["price"])

    save_data()

    if updated_products:
        status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

        for name, prev_price, curr_price in updated_products:
            if curr_price < prev_price:
                status_message += f"{name}: Prezzo calato da {prev_price}€ a {curr_price}€\n"

                notify(name, prev_price, curr_price)
            elif curr_price > prev_price:
                status_message += f"{name}: Prezzo aumentato da {prev_price}€ a {curr_price}€\n"
            else:
                status_message += f"{name}: Prezzo invariato a {curr_price}€\n"

        messagebox.showinfo("Aggiornamento", status_message)

        logger.info("Tutti i prodotti sono stati aggiornati")
    else:
        messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali tutti nuovamente")

        logger.warning("Nessun prodotto è stato aggiornato")


def view_graph_for_product(product_name):
    def create_graph_for_product(product_name):
        global prices

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
            xaxis=dict(
                type='date'
            ),
            hovermode='x'
        )
        
        return fig
    
    global panel_prices, products_tree

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
    global products_to_view, sort_state, columns, products_tree

    items = list(products_to_view.items())
    column_name = columns[col_idx]
    column_key_map = {
        'Nome': lambda item: item[0].lower(),
        'URL': lambda item: item[1]['url'].lower(),
        'Prezzo': lambda item: item[1]['price'] if isinstance(item[1]['price'], (int, float)) else float('inf'),
        'Timer': lambda item: (item[1]['timer'] + item[1]['timer_refresh']) - time.time(),
        'Timer Aggiornamento [s]': lambda item: item[1]['timer_refresh'],
        'Data Inserimento': lambda item: item[1]['date_added'],
        'Data Ultima Modifica': lambda item: item[1]['date_edited']
    }

    if sort_state['column'] == column_name:
        sort_state['order'] = (sort_state['order'] + 1) % 3
    else:
        sort_state['column'] = column_name
        sort_state['order'] = 1  

    if sort_state['order'] == 0:
        # Restore initial order
        items.sort(key=column_key_map["Data Ultima Modifica"])
        sort_state['column'] = None
    elif sort_state['order'] == 1:
        # Sort ascending
        items.sort(key=column_key_map[column_name])
    else:
        # Sort descending
        items.sort(key=column_key_map[column_name], reverse=True)

    # Update the dictionary
    products_to_view = {name: details for name, details in items}

    # Update column heading to reflect sort direction
    for column in columns:
        products_tree.heading(column, text=column, anchor='center')
    if sort_state['order'] != 0:
        sort_indicator = '▲' if sort_state['order'] == 1 else '▼'
        products_tree.heading(column_name, text=f"{column_name} {sort_indicator}", anchor='center')


def update_products_to_view():
    def filter_products(search_text):
        search_text = search_text.lower()
        filtered_products = {name: details for name, details in products.items()
                            if search_text in name.lower()}
        
        return filtered_products
    
    global products, products_to_view

    reset_filters(reset_search_bar=False)

    search_text = search_entry.get()
    if search_text != "":
        products_to_view = filter_products(search_text)
    else:
        products_to_view = products


def show_product_details():
    def calculating_suggestion(all_prices, current_price, price_average, price_minimum, price_maximum):
        if all(x == all_prices[0] for x in all_prices):
            return "Ad oggi non sono state rilevate variazioni di prezzo 😐", "blue"
        elif current_price <= price_minimum:
            return "Ottimo momento per comprare! 🤩", "green"
        elif current_price < price_average * 0.9:
            return "Prezzo inferiore alla media, buon momento per comprare 😊", "green"
        elif current_price >= price_maximum:
            return "Prezzo alto rispetto alla storia, considera di aspettare una riduzione 😔", "red"
        else:
            return "Prezzo nella media, considera se hai bisogno del prodotto ora 😕", "#FFA500"
    
    global products_tree, products, prices, common_font, root

    selected = products_tree.selection()

    if not selected:
        logger.warning("Nessun prodotto selezionato per visualizzare i dettagli")
        return
    
    product_name = selected[0]

    # Estrazione dei dati
    url = products[product_name]["url"]
    current_price = get_last_price(product_name)
    historical_prices = prices.get(product_name, [])
    
    # Calcoli sui prezzi
    all_prices = [entry["price"] for entry in historical_prices if isinstance(entry["price"], (int, float))]
    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = current_price

    text_suggestion, color_suggestion = calculating_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)
    
    # Creazione del pannello dei dettagli
    details_window = tk.Toplevel(root)
    details_window.title(f"Dettagli del prodotto: {product_name}")
    details_window.configure(padx=20, pady=10)  # Aggiunta del padding alla finestra
    details_window.transient(root)
    details_window.grab_set()

    # Configurazione del layout a griglia
    for i in range(5):
        details_window.grid_columnconfigure(i, weight=1)
    
    # Font per il nome del prodotto (grassetto)
    name_font = ('Helvetica', 12, 'bold')
    highlight_font = ('Helvetica', 14, 'bold')  # Font evidenziato per il prezzo corrente
    
    # Creazione di un frame per la riga con il nome e il pulsante del grafico
    top_frame = ttk.Frame(details_window)
    top_frame.pack(fill='x', pady=10)

    # Configurazione della griglia per il frame
    top_frame.grid_columnconfigure(0, weight=1)  # Colonna per il nome del prodotto
    top_frame.grid_columnconfigure(1, weight=1)  # Colonna vuota per spingere il pulsante a destra
    top_frame.grid_columnconfigure(2, weight=0)  # Colonna per il pulsante

    # Nome del prodotto a sinistra
    name_label = ttk.Label(top_frame, text=product_name, font=name_font)
    name_label.grid(row=0, column=0, sticky='w')

    # Pulsante "Visualizza Grafico" all'estrema destra
    view_graph_button = ttk.Button(top_frame, text="Visualizza Grafico", command=lambda: view_graph_for_product(product_name))
    view_graph_button.grid(row=0, column=1, sticky='e')

    # Limita la lunghezza dell'URL e rende cliccabile
    truncated_url = (url[:45] + '...') if len(url) > 45 else url
    url_label = ttk.Label(top_frame, text=truncated_url, font=common_font, foreground="blue", cursor="hand2", wraplength=400)
    url_label.grid(row=1, column=0, sticky='w')
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))  # Apri URL con click

    # Disposizione delle informazioni sui prezzi in un frame
    prices_frame = ttk.Frame(details_window)
    prices_frame.pack(anchor="w", padx=10)

    # Prezzo corrente evidenziato
    current_price_label = ttk.Label(prices_frame, text=f"Prezzo Attuale: {current_price:.2f}€", font=highlight_font, foreground=color_suggestion)
    current_price_label.grid(row=0, column=0, sticky='w', pady=(5, 10))

    # Prezzi storici disposti a griglia
    ttk.Label(prices_frame, text="Prezzo Medio:", font=common_font).grid(row=1, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{average_price:.2f}€", font=common_font).grid(row=1, column=1, sticky='e', pady=5)

    ttk.Label(prices_frame, text="Prezzo Minimo Storico:", font=common_font).grid(row=2, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{price_minimum:.2f}€", font=common_font).grid(row=2, column=1, sticky='e', pady=5)

    ttk.Label(prices_frame, text="Prezzo Massimo Storico:", font=common_font).grid(row=3, column=0, sticky='w', pady=5)
    ttk.Label(prices_frame, text=f"{price_maximum:.2f}€", font=common_font).grid(row=3, column=1, sticky='e', pady=5)
    
    # Suggerimento con colore dinamico
    suggerimento_label = ttk.Label(details_window, text=text_suggestion, font=name_font, foreground=color_suggestion)
    suggerimento_label.pack(pady=10)
    
    ttk.Button(details_window, text="Chiudi", command=details_window.destroy).pack(pady=10)


def show_context_menu(event):
    global products_tree, context_root_menu, multi_selection_menu

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
        context_root_menu.post(event.x_root, event.y_root)


def on_item_click_to_view(event):
    global products_tree

    if len(products_tree.selection()) == 1:
        show_product_details()


def update_buttons_state(event=None):
    global products_to_view, products_tree

    selected_items = products_tree.selection()
    num_selected = len(selected_items)

    if num_selected > 1:
        # Se ci sono più di un elemento selezionato
        remove_button["state"] = "normal"
        update_button["state"] = "normal"
        add_button["state"] = "normal"  # Mantieni attivo anche add_button
        update_all_button["state"] = "normal" if products_to_view else "disabled"

        edit_button["state"] = "disabled"
        view_button["state"] = "disabled"
    elif num_selected == 1:
        # Se c'è un solo elemento selezionato
        remove_button["state"] = "normal"
        update_button["state"] = "normal"
        edit_button["state"] = "normal"
        view_button["state"] = "normal"

        add_button["state"] = "normal"
        update_all_button["state"] = "normal" if products_to_view else "disabled"
    else:
        # Se non ci sono elementi selezionati
        remove_button["state"] = "disabled"
        update_button["state"] = "disabled"
        edit_button["state"] = "disabled"
        view_button["state"] = "disabled"

        add_button["state"] = "normal"
        update_all_button["state"] = "normal" if products_to_view else "disabled"


def periodic_update():
    def refresh_treeview():
        def calculate_time_remaining(last_checked_time, update_interval):
            next_check = last_checked_time + update_interval
            time_remaining = next_check - time.time()
            if time_remaining < 0:
                time_remaining = 0

            hours, remainder = divmod(time_remaining, 3600)
            minutes, seconds = divmod(remainder, 60)

            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        global products_to_view, products_tree
        
        selection = products_tree.selection()
        products_tree.delete(*products_tree.get_children())

        for name in products_to_view:
            timer_text = calculate_time_remaining(products_to_view[name]["timer"], products_to_view[name]["timer_refresh"])
            products_tree.insert("", "end", iid=name, values=(name, products_to_view[name]["url"], str(products_to_view[name]["price"]) + "€", timer_text, products_to_view[name]["timer_refresh"], products_to_view[name]["date_added"], products_to_view[name]["date_edited"]))

        # Ripristina la selezione
        for item_id in selection:
            if item_id in products_tree.get_children():
                products_tree.selection_add(item_id)

    global root

    refresh_treeview()
    update_buttons_state()

    root.after(500, periodic_update)  # Richiama ogni secondo (500 ms)


def select_all(event=None):
    global products_tree

    products_tree.selection_set(products_tree.get_children())


def clear_selection(event=None):
    global products_tree

    # Identifica la riga su cui è avvenuto il clic
    row_id = products_tree.identify_row(event.y)
    
    if row_id:
        # Clic su una riga: non deselezionare nulla
        return
    else:
        # Clic su area vuota: deseleziona tutti gli elementi
        if event.widget == products_tree:
            products_tree.selection_remove(*products_tree.selection())


def navigate_products(event):
    selected_item = products_tree.selection()
    if not selected_item:
        return  # Nessun elemento selezionato

    current_index = products_tree.index(selected_item[0])
    items = products_tree.get_children()

    if event.keysym == 'Down':
        next_index = (current_index + 1) % len(items)  # Vai al prossimo elemento
    elif event.keysym == 'Up':
        next_index = (current_index - 1) % len(items)  # Vai all'elemento precedente
    else:
        return

    products_tree.selection_remove(selected_item)
    products_tree.selection_add(items[next_index])
    products_tree.see(items[next_index])


columns = ("Nome", "URL", "Prezzo", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica")

products_file = "products.json"
products = {}
products_to_view = {}

prices_file = 'prices.json'
prices = {}
panel_prices = None

threads = {}
stop_flags = {}

sort_state = {
    'column': None,
    'order': 0  # 0: no sorting, 1: ascending, 2: descending
}

common_font = ('Arial', 10)

root = tk.Tk()
root.title("Monitoraggio Prezzi Amazon")
root.minsize(1300, 300)

limit_letters = (root.register(lambda s: len(s) <= 50), '%P')

# Frame per l'input dell'utente
input_frame = ttk.Frame(root)
input_frame.pack(fill="x", padx=10, pady=10)

add_button = ttk.Button(input_frame, text="Aggiungi", command=open_add_product_dialog)
add_button.grid(row=2, column=0, padx=5, pady=5, sticky="we")

view_button = ttk.Button(input_frame, text="Visualizza", command=show_product_details, state="disabled")
view_button.grid(row=2, column=1, padx=5, pady=5, sticky="we")

edit_button = ttk.Button(input_frame,text="Modifica",command=open_edit_product_dialog,state="disabled")
edit_button.grid(row=2, column=2, padx=5, pady=5, sticky="we")

remove_button = ttk.Button(input_frame, text="Rimuovi", command=remove_product, state="disabled")
remove_button.grid(row=2, column=3, padx=5, pady=5, sticky="we")

# Colonna vuota per aggiungere spazio tra i bottoni esistenti e quelli nuovi
ttk.Label(input_frame, text="", width=18).grid(row=2, column=4, padx=5, pady=5, sticky="we")

update_button = ttk.Button(input_frame, text="Aggiorna Selezionati", command=update_selected_prices, state="disabled")
update_button.grid(row=2, column=5, padx=5, pady=5, sticky="e")

update_all_button = ttk.Button(input_frame, text="Aggiorna Tutti", command=update_all_prices, state="disabled")
update_all_button.grid(row=2, column=6, padx=5, pady=5, sticky="e")

# Setup della barra di ricerca
search_frame = ttk.Frame(root)
search_frame.pack(fill="x", padx=5, pady=5)

ttk.Label(search_frame, text="Ricerca Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")
search_entry = ttk.Entry(search_frame, width=80, font=common_font, validate='key', validatecommand=limit_letters)
search_entry.grid(row=0, column=1, padx=10, pady=10, sticky='we')
search_entry.update_idletasks()
search_entry.bind("<KeyRelease>", lambda event: update_products_to_view())

# Tabella dei prodotti
frame_products_tree = tk.Frame(root)
frame_products_tree.pack(fill="both", expand=True, padx=10, pady=10)
products_tree = ttk.Treeview(frame_products_tree, columns=columns, show="headings")
for idx, col in enumerate(columns):
    products_tree.heading(col, text=col, anchor='center', command=lambda _idx=idx: sort_by_column(_idx))
    products_tree.column(col, width=200, anchor='center' if col in ["Prezzo", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica"] else 'w')
products_tree.pack(fill="both", expand=True, padx=10, pady=10)

scrollbar = ttk.Scrollbar(frame_products_tree, orient="vertical", command=products_tree.yview)
products_tree.configure(yscrollcommand=scrollbar.set)
products_tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

context_root_menu = tk.Menu(root, tearoff=0)
context_root_menu.add_command(label="Visualizza prodotto", command=show_product_details)
context_root_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog)
context_root_menu.add_command(label="Rimuovi prodotto", command=remove_product)

multi_selection_menu = tk.Menu(root, tearoff=0)
multi_selection_menu.add_command(label="Rimuovi selezionati", command=remove_product)
multi_selection_menu.add_command(label="Aggiorna selezionati", command=update_selected_prices)

products_tree.bind("<Button-3>", show_context_menu)
products_tree.bind("<Control-a>", select_all)
root.bind("<Button-1>", clear_selection)
products_tree.bind("<Double-1>", on_item_click_to_view)
products_tree.bind("<Return>", on_item_click_to_view)
products_tree.bind("<Down>", navigate_products)
products_tree.bind("<Up>", navigate_products)

load_data()
load_prices_data()
periodic_update()

for name in products:
    products[name]['timer'] = time.time()
save_data()

root.mainloop()
