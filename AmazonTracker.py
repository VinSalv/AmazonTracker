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

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logger = logging.getLogger("logger")
logger.setLevel(logging.WARNING)
logger_handler = logging.FileHandler(os.path.join(log_dir, "logger.log"))
logger_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(logger_handler)


def load_config():
    config_file = "config.json"

    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as file:
                config = json.load(file)
                return (
                    config["sender_email"],
                    config["sender_password"],
                    config["receiver_email"],
                    config["url_telegram"],
                    config["chat_id_telegram"],
                )
        except Exception as e:
            logger.error(f"Errore nel caricamento del file di configurazione: {e}")
            messagebox.showerror(
                "Attenzione", "Errore nel caricamento del file di configurazione"
            )
            exit()
    else:
        logger.error(f"File di configurazione '{config_file}' non trovato")
        messagebox.showerror(
            "Attenzione", f"File di configurazione '{config_file}' non trovato"
        )
        exit()


def send_email(subject, body, email_to_notify):
    from_email, from_password, _, _, _ = load_config()

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = email_to_notify
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, from_password)
        server.sendmail(from_email, email_to_notify, msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f"Impossibile inviare l'email: {e}")


def send_notification(subject, body):
    _, _, recipient_email, url_telegram, chat_id_telegram = load_config()

    send_email(subject, body, recipient_email)

    try:
        payload = {"chat_id": chat_id_telegram, "text": body}
        response = requests.post(url_telegram, data=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Impossibile inviare il messaggio Telegram: {e}")


def calculating_suggestion(all_prices, current_price, price_average, price_minimum, price_maximum):
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
    global products_to_view, sort_state

    sort_state = {"column": None, "order": 0}
    column_key_map = {
        "Nome": lambda item: item[0].lower(),
        "URL": lambda item: item[1]["url"].lower(),
        "Prezzo": lambda item: item[1]["price"]
        if isinstance(item[1]["price"], (int, float))
        else float("inf"),
        "Notifica": lambda item: item[1]["notify"],
        "Timer": lambda item: item[1]["timer"],
        "Timer Aggiornamento [s]": lambda item: item[1]["timer_refresh"],
        "Data Inserimento": lambda item: item[1]["date_added"],
        "Data Ultima Modifica": lambda item: item[1]["date_edited"],
    }
    items = list(products_to_view.items())
    items.sort(key=column_key_map["Data Ultima Modifica"])
    products_to_view = {name: details for name, details in items}

    for column in columns:
        products_tree.heading(column, text=column, anchor="center")
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
        title_element = soup.find("span", id="productTitle")

        if title_element is None:
            raise ValueError("Titolo del prodotto non trovato")
        
        title_container = title_element.find_parent()
        price_element = title_container.find_next("span", class_="aok-offscreen")

        if price_element is None:
            raise ValueError("Elemento prezzo non trovato sotto il titolo")
        
        price_text = price_element.get_text().strip()
        match = re.search(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?", price_text)

        if match:
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
            
            if products[name]["notify"]:
                previous_price = get_last_price(name)
                historical_prices = prices.get(name, [])
                all_prices = [
                    entry["price"]
                    for entry in historical_prices
                    if isinstance(entry["price"], (int, float))
                ]

                if all_prices:
                    average_price = round(statistics.mean(all_prices), 2)
                    price_minimum = min(all_prices)
                    price_maximum = max(all_prices)
                else:
                    average_price = price_minimum = price_maximum = current_price

                text_suggestion, _ = calculating_suggestion(
                    all_prices,
                    current_price,
                    average_price,
                    price_minimum,
                    price_maximum,
                )
                subject = "Prezzo in calo!"
                body = (
                    f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n"
                    + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
                    + f"Acquista ora: {products[name]['url']}"
                )

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
                        subject_to_send = "Prezzo inferiore alla soglia indicata!"
                        body_to_send = (
                            f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.\n"
                            + f"Il costo attuale è {current_price}€.\n\n"
                            + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
                            + f"Acquista ora: {products[name]['url']}"
                        )

                    if current_price < value_to_compare:
                        send_email(
                            subject=subject_to_send,
                            body=body_to_send,
                            email_to_notify=key,
                        )

            products[name]["price"] = current_price
            save_prices_data(name, products[name]["price"])
            save_data()

        while not stop_events[name].is_set():  # Continua finché l'evento non è settato
            products[name]["timer"] = time.time()

            if stop_events[name].wait(products[name]["timer_refresh"]):
                break  # Esce immediatamente se l'evento è settato durante il wait

            check_price_and_notify(name, url)
            reset_filters()
        logger.info(f"Monitoraggio di '{name}' fermato")
        threads.pop(name, None)

    global threads, stop_events

    if name in threads and threads[name].is_alive():
        logger.info(f"Fermando il monitoraggio precedente di '{name}'...")
        stop_events[name].set()  # Segnala al thread corrente di fermarsi
        threads[name].join(timeout=1)  # Aspetta che il thread corrente termini

    stop_events[name] = threading.Event()
    timer_thread = threading.Thread(target=track_loop, args=(name, url,), daemon=True,)
    threads[name] = timer_thread
    timer_thread.start()
    logger.info(f"Avviato il monitoraggio per '{name}' ({url}) con un nuovo timer")


def load_data():
    global products, products_to_view

    if os.path.exists(products_file):
        try:
            with open(products_file, "r") as file:
                products = json.load(file)

                for name in products:
                    if not isinstance(products[name], dict):
                        raise Exception("Ogni elemento nel file JSON dei dati articoli deve essere un dizionario")
                    
                    url = products[name].get("url")

                    if not url:
                        raise Exception("Ogni prodotto deve avere un 'url'")
                    
                    start_tracking(name, url)

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
    try:
        global products_to_view

        with open(products_file, "w") as file:
            json.dump(products, file, indent=4)

        products_to_view = products
        logger.info("Dati articoli salvati con successo")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati articoli: {e}")


def load_prices_data():
    global prices

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
            messagebox.showerror("Attenzione","Errore durante il caricamento dei dati monitoraggio prezzi")
            exit()
    else:
        logger.warning(f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")
        messagebox.showwarning("Attenzione",f"File dei dati monitoraggio prezzi '{prices_file}' non trovato")


def save_prices_data(name, price):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price_entry = {"price": price, "date": current_time}

    if name not in prices:
        prices[name] = []

    prices[name].append(price_entry)

    try:
        with open(prices_file, "w") as file:
            json.dump(prices, file, indent=4)
        logger.info(f"Salvato aggiornamento prezzo per {name}: {price}€ al {current_time}")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati monitoraggio prezzi: {e}")


def center_window(window):
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_text_menu(event, widget, onlyRead=False):
    def is_text_selected(widget):
        try:
            if isinstance(widget, tk.Text):
                return widget.tag_ranges(tk.SEL) != ()
            elif isinstance(widget, ttk.Entry):
                return widget.selection_present()
        except tk.TclError:
            return False
        return False

    def is_clipboard_available():
        try:
            return bool(root.clipboard_get())
        except tk.TclError:
            return False

    def copy_text(widget):
        try:
            if isinstance(widget, tk.Label):
                root.clipboard_clear()
                root.clipboard_append(widget.cget("text"))  # Copia il testo della label
            else:
                widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def cut_text(widget):
        try:
            widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def paste_text(widget):
        try:
            widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    text_menu = tk.Menu(root, tearoff=0)

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

    text_menu.tk_popup(event.x_root, event.y_root)


def open_add_product_dialog():
    def on_entry_focus_in(event):
        update_suggestions()

    def on_entry_focus_out(event):
        listbox_frame.place_forget()

    def update_suggestions(*args):
        typed_text = name_entry_var.get().strip().lower()
        listbox_suggestions.delete(0, tk.END)

        if typed_text:
            matching_suggestions = [name for name in prices.keys() if typed_text in name.lower()]

            if name_entry.get() not in matching_suggestions:
                listbox_suggestions.insert(tk.END, name_entry.get())

            for suggestion in matching_suggestions:
                listbox_suggestions.insert(tk.END, suggestion)

            listbox_suggestions.config(height=min(len(matching_suggestions), 5))
            x = name_entry.winfo_x()
            y = name_entry.winfo_y() + name_entry.winfo_height()
            listbox_frame.place(x=x, y=y, anchor="nw")
            listbox_suggestions.lift()
        else:
            listbox_frame.place_forget()

    def on_select_suggestion(event):
        selection = listbox_suggestions.curselection()

        if selection:
            selected_name = listbox_suggestions.get(selection[0])
            name_entry.delete(0, tk.END)
            name_entry.insert(0, selected_name)
            listbox_frame.place_forget()

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
                table.insert("", "end", iid=key, values=(key, str(value) + "€"))

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
            new_threshold = simpledialog.askstring(
                "Modifica Soglia", f"Soglia di notifica per '{email}':"
            )
            new_threshold = new_threshold.replace(" ", "")

            if new_threshold == "":
                new_threshold = 0.0

            try:
                emails_and_thresholds[email] = float(new_threshold)
                update_table()
            except:
                messagebox.showwarning(
                    "Attenzione", "Inserisci una soglia valida (numerica) oppure 0"
                )

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
        advanced_dialog.transient(root)
        advanced_dialog.grab_set()
        
        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(
            row=0, column=0, padx=10, pady=10, sticky="we"
        )

        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))

        ttk.Label(container, text="Soglia:").grid(
            row=1, column=0, padx=10, pady=10, sticky="we"
        )

        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(lambda s: s.isdigit() or s in [".", "-"]), "%S"))

        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        table = ttk.Treeview(container, columns=("Email", "Soglia"), show="headings")
        table.grid(row=3, column=0, columnspan=2, pady=10, sticky="nsew")
        table.heading("Email", text="Email")
        table.heading("Soglia", text="Soglia")
        table.column("Email", width=200)
        table.column("Soglia", width=100)
        vsb = ttk.Scrollbar(container, orient="vertical", command=table.yview)
        vsb.grid(row=3, column=2, sticky="ns")
        table.configure(yscrollcommand=vsb.set)
        table.bind("<Button-3>", show_context_menu)

        context_menu = tk.Menu(advanced_dialog, tearoff=0)
        context_menu.add_command(label="Modifica Soglia", command=modify_threshold)
        context_menu.add_command(label="Rimuovi Email", command=remove_email)
        
        update_table()

        ttk.Label(container, text="Timer [s]:").grid(row=4, column=0, padx=10, pady=10, sticky="we")

        timer_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(validate_timer_input), "%P"))
        timer_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        timer_entry.insert(0, timer_refresh)
        timer_entry.bind("<KeyRelease>", on_timer_change)
        timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))

        center_window(advanced_dialog)

    def add_product(name, url):
        if not name or not url:
            messagebox.showwarning("Attenzione", "Compila tutti i campi!")
            return False
        
        for existing_name in products:
            if name == existing_name:
                messagebox.showwarning("Attenzione", "Il nome del prodotto è già presente!\nCambia il nome")
                return False
            
            if url == products[existing_name]["url"]:
                messagebox.showwarning("Attenzione", "Questo articolo è già in monitoraggio!\nCambia url")
                return False
            
        current_price = get_price(url)

        if current_price is None:
            current_price = "Aggiorna o verifica url: - "
            messagebox.showwarning("Attenzione", "Non è stato trovato il prezzo sulla pagina!\nAggiorna o verifica url")

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

        save_data()
        save_prices_data(name, products[name]["price"])

        start_tracking(name, url)

        reset_filters()

        logger.info(f"Prodotto '{name}' aggiunto con successo")

        add_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    emails_and_thresholds = {}
    timer_refresh = 1800

    notify = tk.BooleanVar(value=True)

    add_product_dialog = tk.Toplevel(root)
    add_product_dialog.title("Aggiungi Prodotto")
    add_product_dialog.resizable(False, False)
    add_product_dialog.transient(root)
    add_product_dialog.grab_set()
    
    container = ttk.Frame(add_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    name_entry_var = tk.StringVar()
    name_entry_var.trace_add("write", update_suggestions)
    name_entry = ttk.Entry(container, width=80, font=common_font, textvariable=name_entry_var, validate="key", validatecommand=limit_letters)
    name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    name_entry.bind("<Button-3>", lambda e: show_text_menu(e, name_entry))

    listbox_frame = ttk.Frame(add_product_dialog)
    listbox_frame.place_forget()
    listbox_suggestions = tk.Listbox(listbox_frame, width=80)
    listbox_suggestions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_suggestions.bind("<<ListboxSelect>>", on_select_suggestion)
    listbox_suggestions.bind("<FocusOut>", lambda e: listbox_frame.place_forget())
    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox_suggestions.yview)
    scrollbar.pack(side="right", fill="y")
    listbox_suggestions.config(yscrollcommand=scrollbar.set)

    name_entry.bind("<FocusIn>", on_entry_focus_in)
    name_entry.bind("<FocusOut>", on_entry_focus_out)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")
    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)
    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")
    ttk.Button(container, text="Aggiungi", command=lambda: add_product(name_entry.get().strip().lower(), url_text.get("1.0", "end-1c").strip()),).grid(row=3, column=1, pady=10, sticky="e")

    center_window(add_product_dialog)


def open_edit_product_dialog():
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
                table.insert("", "end", iid=key, values=(key, str(value) + "€"))

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
            new_threshold = simpledialog.askstring(
                "Modifica Soglia", f"Soglia di notifica per '{email}':"
            )
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
        advanced_dialog.transient(root)
        advanced_dialog.grab_set()

        container = ttk.Frame(advanced_dialog, padding="10")
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(container, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

        email_entry = ttk.Entry(container, width=40, font=common_font)
        email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        email_entry.bind("<Button-3>", lambda e: show_text_menu(e, email_entry))

        ttk.Label(container, text="Soglia:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

        threshold_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(lambda s: s.isdigit() or s in [".", "-"]), "%S"))
        threshold_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        threshold_entry.bind("<Button-3>", lambda e: show_text_menu(e, threshold_entry))

        add_button = ttk.Button(container, text="Aggiungi", command=add_email_threshold)
        add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="e")

        table = ttk.Treeview(container, columns=("Email", "Soglia"), show="headings")
        table.grid(row=3, column=0, columnspan=2, pady=10, sticky="nsew")
        table.heading("Email", text="Email")
        table.heading("Soglia", text="Soglia")
        table.column("Email", width=200)
        table.column("Soglia", width=100)
        vsb = ttk.Scrollbar(container, orient="vertical", command=table.yview)
        vsb.grid(row=3, column=2, sticky="ns")
        table.configure(yscrollcommand=vsb.set)

        context_menu = tk.Menu(advanced_dialog, tearoff=0)
        context_menu.add_command(label="Modifica Soglia", command=modify_threshold)
        context_menu.add_command(label="Rimuovi Email", command=remove_email)

        table.bind("<Button-3>", show_context_menu)

        ttk.Label(container, text="Timer [s]:").grid(row=4, column=0, padx=10, pady=10, sticky="we")
        
        timer_entry = ttk.Entry(container, width=20, font=common_font, validate="key", validatecommand=(root.register(validate_timer_input), "%P"))
        timer_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        timer_entry.insert(0, timer_refresh)
        timer_entry.bind("<KeyRelease>", on_timer_change)
        timer_entry.bind("<Button-3>", lambda e: show_text_menu(e, timer_entry))
        
        update_table()

        center_window(advanced_dialog)

    def edit_product(name, current_url, new_url):
        if not new_url:
            messagebox.showwarning("Attenzione", "Compila l'URL!")
            return False
        
        if current_url != new_url:
            for existing_name in products:
                if new_url == products[existing_name]["url"]:
                    messagebox.showwarning("Attenzione", "Questo articolo è già in monitoraggio!\nCambia l'URL")
                    return False
                
        new_price = get_price(new_url)

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

        save_data()
        save_prices_data(name, products[name]["price"])

        start_tracking(name, new_url)
        reset_filters()

        logger.info(f"Prodotto '{name}' modificato con successo")

        edit_product_dialog.destroy()

    global emails_and_thresholds, timer_refresh, notify

    selected_item = products_tree.selection()[0]
    selected_name = products_tree.item(selected_item)["values"][0]
    selected_url = products[selected_name]["url"]

    emails_and_thresholds = products[selected_name]["emails_and_thresholds"]
    timer_refresh = products[selected_name]["timer_refresh"]

    notify = tk.BooleanVar(value=products[selected_name]["notify"])

    edit_product_dialog = tk.Toplevel(root)
    edit_product_dialog.title("Modifica Prodotto")
    edit_product_dialog.resizable(False, False)
    edit_product_dialog.transient(root)
    edit_product_dialog.grab_set()

    container = ttk.Frame(edit_product_dialog, padding="10")
    container.grid(row=0, column=0, sticky="nsew")

    ttk.Label(container, text="Nome Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

    text_widget = tk.Text(container, font=common_font, height=1, width=80, wrap="none", bd=0, bg="white")
    text_widget.insert(tk.END, selected_name)
    text_widget.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    text_widget.bind("<Button-3>", lambda e: show_text_menu(e, text_widget, True))
    text_widget.config(state=tk.DISABLED)

    ttk.Label(container, text="URL Prodotto:").grid(row=1, column=0, padx=10, pady=10, sticky="we")

    text_frame = ttk.Frame(container)
    text_frame.grid(row=1, column=1, padx=10, pady=10, sticky="we")

    url_text = tk.Text(text_frame, height=5, width=80, font=common_font)
    url_text.pack(side="left", fill="both", expand=True)
    url_text.insert("1.0", selected_url)
    url_text.bind("<Button-3>", lambda e: show_text_menu(e, url_text))
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=url_text.yview)
    scrollbar.pack(side="right", fill="y")
    url_text.config(yscrollcommand=scrollbar.set)

    ttk.Label(container, text="Notifiche:").grid(row=2, column=0, padx=10, pady=10, sticky="w")

    notify_checkbutton = ttk.Checkbutton(container, variable=notify)
    notify_checkbutton.grid(row=2, column=1, padx=10, pady=10, sticky="we")

    ttk.Button(container, text="Avanzate", command=open_advanced_dialog).grid(row=3, column=0, pady=10, sticky="w")
    ttk.Button(container, text="Salva", command=lambda: edit_product(selected_name, selected_url, url_text.get("1.0", "end-1c").strip())).grid(row=3, column=1, pady=10, sticky="e")

    center_window(edit_product_dialog)


def remove_products():
    def stop_tracking(name):
        if name in stop_events:
            stop_events[name].set()  # Setta l'evento di stop per fermare il monitoraggio

        if name in threads:
            threads[name].join(timeout=1)  # Attende la terminazione del thread

        if name in stop_events:
            del stop_events[name]

    global stop_events, threads

    selected = products_tree.selection()

    if not selected:
        logger.warning("Seleziona un prodotto dalla lista per rimuoverlo")
        return
    
    num_selected = len(selected)
    response = messagebox.askyesno("Conferma rimozione", f"Sei sicuro di voler rimuovere i {num_selected} prodotti selezionati?" if num_selected > 1 else f"Sei sicuro di voler rimuovere il prodotto selezionato?")
    
    if response:
        reset_filters()

        for name in selected:
            if name in products:
                del products[name]
                save_data()
                stop_tracking(name)
                logger.info(f"Prodotto '{name}' rimosso con successo")
            else:
                logger.warning(f"Il prodotto '{name}' non è presente nella lista")


def send_notification_and_email(name, previous_price, current_price):
    historical_prices = prices.get(name, [])
    all_prices = [entry["price"] for entry in historical_prices if isinstance(entry["price"], (int, float))]

    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = current_price

    text_suggestion, _ = calculating_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)
    subject = "Prezzo in calo!"
    body = (
        f"Il prezzo dell'articolo '{name}' è sceso da {previous_price}€ a {current_price}€.\n\n"
        + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
        + f"Acquista ora: {products[name]['url']}"
    )

    send_notification(subject=subject, body=body)

    for email, threshold in products[name]["emails_and_thresholds"].items():
        value_to_compare = previous_price
        subject_to_send = subject
        body_to_send = body

        if threshold != 0.0:
            value_to_compare = threshold
            subject_to_send = "Prezzo inferiore alla soglia indicata!"
            body_to_send = (
                f"Il prezzo dell'articolo '{name}' è al di sotto della soglia di {value_to_compare}€ indicata.\n"
                + f"Il costo attuale è {current_price}€.\n\n"
                + f"Dettagli:\n\t- Prezzo medio: {average_price}€\n\t- Prezzo minimo storico: {price_minimum}€\n\t- Prezzo massimo storico: {price_maximum}€\n\n{text_suggestion}\n\n"
                + f"Acquista ora: {products[name]['url']}"
            )

        if current_price < value_to_compare:
            send_email(subject=subject_to_send, body=body_to_send, email_to_notify=email)


def open_progress_dialog(update_all=True):
    def update_prices_threaded(dialog, update_all=True):
        def update_selected_prices(dialog):
            selected = products_tree.selection()

            if not selected:
                logger.warning("Nessun prodotto selezionato per aggiornare il prezzo")
                return
            
            max_value = len(selected)
            dialog.progress_bar["maximum"] = max_value
            dialog.progress_bar["value"] = 0
            updated_products = []

            for i, name in enumerate(selected):
                dialog.progress_bar["value"] = i + 1
                dialog.progress_label.config(text=f"Aggiornamento di {i + 1}/{max_value}...")
                dialog.update_idletasks()

                current_price = get_price(products[name]["url"])

                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    products[name]["price"] = "Aggiorna o verifica url: - "
                    products[name]["timer"] = time.time()
                    products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    continue

                products[name]["price"] = current_price
                products[name]["timer"] = time.time()
                products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                previous_price = get_last_price(name)

                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price, products[name]["notify"]))

                save_prices_data(name, products[name]["price"])

            save_data()

            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, previous_price, current_price, notify in updated_products:
                    if current_price < previous_price:
                        status_message += (f"{name}: Prezzo calato da {previous_price}€ a {current_price}€\n")

                        if notify:
                            send_notification_and_email(name, previous_price, current_price)
                    elif current_price > previous_price:
                        status_message += f"{name}: Prezzo aumentato da {previous_price}€ a {current_price}€\n"
                    else:
                        status_message += f"{name}: Prezzo invariato a {current_price}€\n"

                messagebox.showinfo("Aggiornamento", status_message)
                logger.info("I prodotti selezionati sono stati aggiornati")
            else:
                messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali nuovamente")
                logger.warning("Nessun prodotto selezionato è stato aggiornato")

        def update_all_prices(dialog):
            max_value = len(products)
            dialog.progress_bar["maximum"] = max_value
            dialog.progress_bar["value"] = 0
            updated_products = []

            for i, name in enumerate(products):
                dialog.progress_bar["value"] = i + 1
                dialog.progress_label.config(text=f"Aggiornamento di {i + 1}/{max_value}...")
                dialog.update_idletasks()

                current_price = get_price(products[name]["url"])

                if current_price is None:
                    logger.warning(f"Prodotto '{name}' non aggiornato: non trovato il prezzo sulla pagina {products[name]['url']}")
                    products[name]["price"] = "Aggiorna o verifica url: - "
                    products[name]["timer"] = time.time()
                    products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    continue

                products[name]["price"] = current_price
                products[name]["timer"] = time.time()
                products[name]["date_edited"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                previous_price = get_last_price(name)

                if previous_price is not None:
                    updated_products.append((name, previous_price, current_price, products[name]["notify"]))

                save_prices_data(name, products[name]["price"])

            save_data()

            if updated_products:
                status_message = "Prezzi aggiornati per i seguenti prodotti:\n\n"

                for name, previous_price, current_price, notify in updated_products:
                    if current_price < previous_price:
                        status_message += (f"{name}: Prezzo calato da {previous_price}€ a {current_price}€\n")

                        if notify:
                            send_notification_and_email(name, previous_price, current_price)
                    elif current_price > previous_price:
                        status_message += f"{name}: Prezzo aumentato da {previous_price}€ a {current_price}€\n"
                    else:
                        status_message += f"{name}: Prezzo invariato a {current_price}€\n"

                messagebox.showinfo("Aggiornamento", status_message)
                logger.info("Tutti i prodotti sono stati aggiornati")
            else:
                messagebox.showwarning("Attenzione", "Nessun prezzo aggiornato!\nAggiornali tutti nuovamente")
                logger.warning("Nessun prodotto è stato aggiornato")

        try:
            set_enable_update(False)

            reset_filters()

            root.resizable(False, False)
            root.wm_attributes("-disabled", True)
            
            if update_all:
                update_all_prices(dialog)
            else:
                update_selected_prices(dialog)
        finally:
            set_enable_update()

            reset_timers()

            dialog.destroy()

            root.resizable(True, True)
            root.wm_attributes("-disabled", False)

    dialog = tk.Toplevel(root)
    dialog.grab_set()  # Impedisce l'interazione con la finestra principale
    dialog.overrideredirect(True)
    dialog.resizable(False, False)

    width = 300
    height = 100
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_x = int((screen_width / 2) - (width / 2))
    position_y = int((screen_height / 2) - (height / 2))
    dialog.geometry(f"{width}x{height}+{position_x}+{position_y}")

    progress_label = tk.Label(dialog, text="Inizio aggiornamento...")
    progress_label.pack(pady=10)
    progress_bar = ttk.Progressbar(dialog, orient="horizontal", length=250, mode="determinate")
    progress_bar.pack(pady=10)

    dialog.progress_bar = progress_bar
    dialog.progress_label = progress_label

    thread = threading.Thread(target=update_prices_threaded, args=(dialog, update_all))
    thread.start()

    dialog.wait_window()


def sort_by_column(col_idx):
    global products_to_view

    items = list(products_to_view.items())
    column_name = columns[col_idx]
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

    if sort_state["column"] == column_name:
        sort_state["order"] = (sort_state["order"] + 1) % 3
    else:
        sort_state["column"] = column_name
        sort_state["order"] = 1

    if sort_state["order"] == 0:
        items.sort(key=column_key_map["Data Ultima Modifica"])
        sort_state["column"] = None
    elif sort_state["order"] == 1:
        items.sort(key=column_key_map[column_name])
    else:
        items.sort(key=column_key_map[column_name], reverse=True)

    products_to_view = {name: details for name, details in items}

    for column in columns:
        products_tree.heading(column, text=column, anchor="center")

    if sort_state["order"] != 0:
        sort_indicator = "▲" if sort_state["order"] == 1 else "▼"
        products_tree.heading(column_name, text=f"{column_name} {sort_indicator}", anchor="center")


def update_products_to_view():
    def filter_products(search_text):
        search_text = search_text.lower()
        filtered_products = {name: details for name, details in products.items() if search_text in name.lower()}
        return filtered_products

    global products_to_view

    reset_filters(reset_search_bar=False)

    search_text = search_entry.get()

    if search_text != "":
        products_to_view = filter_products(search_text)
    else:
        products_to_view = products


def show_product_details(event=None):
    def open_view_graph_panel(name):
        def view_graph_for_product(name):
            def create_graph_for_product(name):
                if name not in prices:
                    raise ValueError(f"Prodotto '{name}' non trovato in prices")
                
                df = pd.DataFrame(prices[name])
                df["date"] = pd.to_datetime(df["date"])
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df["date"], y=df["price"], mode="lines+markers", name=name, hovertemplate="Date: %{x}<br>Price: %{y}<extra></extra>"))
                fig.update_layout(title=f"Prezzi del Prodotto: {name}", xaxis_title="Data", yaxis_title="Prezzo", xaxis=dict(type="date"), hovermode="x")
                
                return fig

            def disable_tkinter_windows(root):
                for window in root.winfo_children():
                    try:
                        window.attributes("-disabled", True)
                    except:
                        pass

                root.attributes("-disabled", True)

            def enable_tkinter_windows(root):
                for window in root.winfo_children():
                    try:
                        window.attributes("-disabled", False)
                    except:
                        pass

                root.attributes("-disabled", False)

            global panel_prices

            if panel_prices is None:
                panel_prices = QApplication([])

            fig = create_graph_for_product(name)
            html_str = pio.to_html(fig, full_html=True)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
                temp_file.write(html_str.encode("utf-8"))
                temp_file.flush()
                temp_file_path = temp_file.name

            disable_tkinter_windows(root)

            qMainWindow = QMainWindow()
            qMainWindow.setWindowTitle(f"Grafico Prezzi - {name}")

            central_widget = QWidget()

            qVBoxLayout = QVBoxLayout(central_widget)
            qMainWindow.setCentralWidget(central_widget)

            web_view = QWebEngineView()
            web_view.setUrl(QUrl.fromLocalFile(temp_file_path))

            qVBoxLayout.addWidget(web_view)

            qMainWindow.resize(800, 600)
            qMainWindow.setWindowModality(2)  # Imposta la finestra in modalità applicazione (blocco finestra Tkinter)
            qMainWindow.show()

            def on_close(event):
                enable_tkinter_windows(root)

                os.remove(temp_file_path)

                web_view.setParent(None)
                web_view.deleteLater()
                panel_prices.quit()

            qMainWindow.closeEvent = on_close

            panel_prices.exec_()

        try:
            set_enable_update(False)
            view_graph_for_product(name)
        finally:
            set_enable_update()

    def copy_to_clipboard(text, show_info=False):
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
    
    name = selected[0]
    url = products[name]["url"]
    current_price = products[name]["price"]
    historical_prices = prices.get(name, [])
    all_prices = [entry["price"] for entry in historical_prices if isinstance(entry["price"], (int, float))]

    if all_prices:
        average_price = round(statistics.mean(all_prices), 2)
        price_minimum = min(all_prices)
        price_maximum = max(all_prices)
    else:
        average_price = price_minimum = price_maximum = current_price

    text_suggestion, color_suggestion = calculating_suggestion(all_prices, current_price, average_price, price_minimum, price_maximum)
    
    details_window = tk.Toplevel(root)
    details_window.title(f"Dettagli del prodotto: {name}")
    details_window.minsize(500, 300)
    details_window.configure(padx=20, pady=10)  # Padding per la finestra
    details_window.transient(root)
    details_window.grab_set()

    for i in range(5):
        details_window.grid_columnconfigure(i, weight=1)

    name_font = ("Helvetica", 12, "bold")
    highlight_font = ("Helvetica", 14, "bold")

    top_frame = ttk.Frame(details_window)
    top_frame.pack(fill="x", pady=10)
    top_frame.grid_columnconfigure(0, weight=1)
    top_frame.grid_columnconfigure(1, weight=1)
    top_frame.grid_columnconfigure(2, weight=0)

    name_label = ttk.Label(top_frame, text=name, font=name_font)
    name_label.grid(row=0, column=0, sticky="w")

    view_graph_button = ttk.Button(top_frame, text="Visualizza Grafico", command=lambda: open_view_graph_panel(name))
    view_graph_button.grid(row=0, column=1, sticky="e")

    truncated_url = (url[:45] + "...") if len(url) > 45 else url

    url_label = ttk.Label(top_frame, text=truncated_url, font=common_font, foreground="blue", cursor="hand2")
    url_label.grid(row=1, column=0, sticky="w")
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    copy_image_label = ttk.Button(top_frame, text="Copia Url", command=lambda: copy_to_clipboard(url))
    copy_image_label.grid(row=1, column=1, sticky="e")

    prices_frame = ttk.Frame(details_window)
    prices_frame.pack(anchor="w", padx=10)

    current_price_label = ttk.Label(prices_frame, text=f"Prezzo Attuale: {current_price:.2f}€" if isinstance(current_price, (int, float)) else "Prezzo Attuale: -", font=highlight_font, foreground=color_suggestion)
    current_price_label.grid(row=0, column=0, sticky="w", pady=(5, 10))
    
    ttk.Label(prices_frame, text="Prezzo Medio:", font=common_font).grid(row=1, column=0, sticky="w", pady=5)

    ttk.Label(prices_frame, text=f"{average_price:.2f}€" if isinstance(average_price, (int, float)) else "-", font=common_font).grid(row=1, column=1, sticky="e", pady=5)
    ttk.Label(prices_frame, text="Prezzo Minimo Storico:", font=common_font).grid(row=2, column=0, sticky="w", pady=5)
    ttk.Label(prices_frame, text=f"{price_minimum:.2f}€" if isinstance(price_minimum, (int, float)) else "-", font=common_font).grid(row=2, column=1, sticky="e", pady=5)
    ttk.Label(prices_frame, text="Prezzo Massimo Storico:", font=common_font).grid(row=3, column=0, sticky="w", pady=5)
    ttk.Label(prices_frame, text=f"{price_maximum:.2f}€" if isinstance(price_maximum, (int, float)) else "-", font=common_font).grid(row=3, column=1, sticky="e", pady=5)
    
    suggerimento_label = ttk.Label(details_window, text=text_suggestion, font=name_font, foreground=color_suggestion)
    suggerimento_label.pack(pady=10)

    ttk.Button(details_window, text="Chiudi", command=details_window.destroy).pack(pady=10)

    details_window.update_idletasks()


def show_context_menu(event):
    x, y = event.x, event.y
    item = products_tree.identify_row(y)

    if item:
        if not products_tree.selection() or item not in products_tree.selection():
            products_tree.selection_set(item)
            products_tree.focus(item)

    selected_items = products_tree.selection()

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
            products_tree.selection_remove(*products_tree.selection())
            products_tree.selection_add(items[current_index])
        else:  # Se Ctrl è premuto
            if items[current_index] in products_tree.selection():
                products_tree.selection_remove(items[current_index])
            else:
                products_tree.selection_add(items[current_index])


def shift_click_products(event):
    global current_index

    products_tree.selection_remove(*products_tree.selection())
    item_id = products_tree.identify_row(event.y)
    items = products_tree.get_children()

    if not item_id:
        return
    
    if current_index is None:
        current_index = 0

    clicked_index = items.index(item_id)
    start = min(current_index, clicked_index)
    end = max(current_index, clicked_index)

    for i in range(start, end + 1):
        products_tree.selection_add(items[i])


def navigate_products(event):
    global current_index

    selected_items = products_tree.selection()

    if not selected_items:
        return
    
    items = products_tree.get_children()
    selected_indices = [products_tree.index(item) for item in selected_items]
    selected_indices.sort()
    is_consecutive = True

    for i in range(1, len(selected_indices)):
        if (selected_indices[i] != selected_indices[i - 1] + 1 or current_index not in selected_indices):
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

    if event.keysym == "Down":
        next_index = current_index = min(current_index + 1, len(items) - 1)
    elif event.keysym == "Up":
        next_index = current_index = max(current_index - 1, 0)
    else:
        return
    
    if event.state & 0x0001:  # Tasto shift premuto
        if items[next_index] in selected_items:
            if next_index != 0 and next_index != len(items) - 1:
                products_tree.selection_remove(items[temp_index])
        else:
            products_tree.selection_add(items[next_index])
    else:
        products_tree.selection_remove(selected_items)
        products_tree.selection_add(items[next_index])

    products_tree.see(items[next_index])


def select_all_products(event=None):
    global current_index

    products_tree.selection_set(products_tree.get_children())
    current_index = None


def clear_selected_products(event=None):
    global current_index

    row_id = products_tree.identify_row(event.y)

    if not row_id:
        if event.widget == products_tree:
            products_tree.selection_remove(*products_tree.selection())
            current_index = None


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

        selection = products_tree.selection()
        products_tree.delete(*products_tree.get_children())

        for name in products_to_view:
            timer_text = calculate_time_remaining(products_to_view[name]["timer"], products_to_view[name]["timer_refresh"])
            products_tree.insert("", "end", iid=name, 
                                 values=(name,products_to_view[name]["url"], 
                                         f"{str(products_to_view[name]['price'])}€",
                                        "Si" if products_to_view[name]["notify"] else "No",
                                        timer_text,
                                        products_to_view[name]["timer_refresh"],
                                        products_to_view[name]["date_added"],
                                        products_to_view[name]["date_edited"]
                                        ))
            
        for item_id in selection:
            if item_id in products_tree.get_children():
                products_tree.selection_add(item_id)

    def update_buttons_state():
        selected_items = products_tree.selection()
        num_selected = len(selected_items)

        if num_selected > 1:
            remove_button["state"] = "normal"
            update_button["state"] = "normal"
            add_button["state"] = "normal"  # Mantieni attivo anche add_button
            update_all_button["state"] = "normal" if products_to_view else "disabled"
            edit_button["state"] = "disabled"
            view_button["state"] = "disabled"
        elif num_selected == 1:
            remove_button["state"] = "normal"
            update_button["state"] = "normal"
            edit_button["state"] = "normal"
            view_button["state"] = "normal"
            add_button["state"] = "normal"
            update_all_button["state"] = "normal" if products_to_view else "disabled"
        else:
            remove_button["state"] = "disabled"
            update_button["state"] = "disabled"
            edit_button["state"] = "disabled"
            view_button["state"] = "disabled"
            add_button["state"] = "normal"
            update_all_button["state"] = "normal" if products_to_view else "disabled"

    if enable_update:
        refresh_treeview()

        update_buttons_state()

        root.after(500, periodic_update)  # Ogni 500 millisecondi


def set_enable_update(update=True):
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

        reset_timers()

        periodic_update()

        enable_controls()
    else:
        disable_controls()

        enable_update = False

        for name in products:
            stop_events[name].set()  # Segnala al thread corrente di fermarsi
            threads[name].join(timeout=1)  # Aspetta che il thread corrente termini


def reset_timers():
    for name in products:
        start_tracking(name, products[name]["url"])

    save_data()


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

products_file = "products.json"
products = {}
products_to_view = {}

prices_file = "prices.json"
prices = {}
panel_prices = None

threads = {}
stop_events = {}

sort_state = {
    "column": None,
    "order": 0,  # 0: nessun ordinamento, 1: crescente, 2: decrescente
}

common_font = ("Arial", 10)

current_index = None

enable_update = True

root = tk.Tk()
root.title("Monitoraggio Prezzi Amazon")
root.minsize(1300, 300)
root.wm_state("zoomed")

limit_letters = (root.register(lambda s: len(s) <= 50), "%P")

input_frame = ttk.Frame(root)
input_frame.pack(fill="x", padx=10, pady=(15, 0))

add_button = ttk.Button(input_frame, text="Aggiungi", command=open_add_product_dialog)
add_button.grid(row=2, column=0, padx=5, pady=5, sticky="we")

view_button = ttk.Button(input_frame, text="Visualizza", command=show_product_details, state="disabled")
view_button.grid(row=2, column=1, padx=5, pady=5, sticky="we")

edit_button = ttk.Button(input_frame, text="Modifica", command=open_edit_product_dialog, state="disabled")
edit_button.grid(row=2, column=2, padx=5, pady=5, sticky="we")

remove_button = ttk.Button(input_frame, text="Rimuovi", command=remove_products, state="disabled")
remove_button.grid(row=2, column=3, padx=5, pady=5, sticky="we")

ttk.Label(input_frame, text="", width=18).grid(row=2, column=4, padx=5, pady=5, sticky="we")

update_button = ttk.Button(input_frame, text="Aggiorna Selezionati", command=lambda: open_progress_dialog(False), state="disabled")
update_button.grid(row=2, column=5, padx=5, pady=5, sticky="e")
update_all_button = ttk.Button(input_frame, text="Aggiorna Tutti", command=lambda: open_progress_dialog(), state="disabled")
update_all_button.grid(row=2, column=6, padx=5, pady=5, sticky="e")

search_frame = ttk.Frame(root)
search_frame.pack(fill="x", padx=5, pady=0)

ttk.Label(search_frame, text="Ricerca Prodotto:").grid(row=0, column=0, padx=10, pady=10, sticky="we")

search_entry = ttk.Entry(search_frame, width=80, font=common_font, validate="key", validatecommand=limit_letters)
search_entry.grid(row=0, column=1, padx=10, pady=10, sticky="we")
search_entry.update_idletasks()
search_entry.bind("<KeyRelease>", lambda event: update_products_to_view())
search_entry.bind("<Button-3>", lambda e: show_text_menu(e, search_entry))

frame_products_tree = tk.Frame(root)
frame_products_tree.pack(fill="both", expand=True, padx=(15, 10), pady=(10, 0))

products_tree = ttk.Treeview(frame_products_tree, columns=columns, show="headings", selectmode="none")

for idx, col in enumerate(columns):
    products_tree.heading(col, text=col, anchor="center", command=lambda _idx=idx: sort_by_column(_idx))
    products_tree.column(col, width=80 if col in ["Notifica"] else 200, anchor="center" if col in ["Prezzo", "Notifica", "Timer", "Timer Aggiornamento [s]", "Data Inserimento", "Data Ultima Modifica"] else "w")

scrollbar = ttk.Scrollbar(frame_products_tree, orient="vertical", command=products_tree.yview)
products_tree.configure(yscrollcommand=scrollbar.set)
products_tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

frame_footer = tk.Frame(root)
frame_footer.pack(side="bottom", fill="x", padx=(20, 40), pady=2)

creator_label = tk.Label(frame_footer, text="Prodotto da Vincenzo Salvati", font=("Arial", 8))
creator_label.pack(side="right")

single_selection_menu = tk.Menu(root, tearoff=0)
single_selection_menu.add_command(label="Visualizza prodotto", command=show_product_details)
single_selection_menu.add_command(label="Modifica prodotto", command=open_edit_product_dialog)
single_selection_menu.add_command(label="Rimuovi prodotto", command=remove_products)

multi_selection_menu = tk.Menu(root, tearoff=0)
multi_selection_menu.add_command(label="Rimuovi selezionati", command=remove_products)
multi_selection_menu.add_command(label="Aggiorna selezionati", command=lambda: open_progress_dialog(False))

products_tree.bind("<Double-1>", show_product_details)
products_tree.bind("<Return>", show_product_details)
products_tree.bind("<Button-3>", show_context_menu)
products_tree.bind("<Button-1>", click_products)
products_tree.bind("<Shift-Button-1>", shift_click_products)
products_tree.bind("<Down>", navigate_products)
products_tree.bind("<Up>", navigate_products)

root.bind("<Control-a>", select_all_products)
root.bind("<Button-1>", clear_selected_products)

load_data()
load_prices_data()

periodic_update()

root.mainloop()
