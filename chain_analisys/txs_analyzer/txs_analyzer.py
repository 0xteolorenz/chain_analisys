import psycopg2
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import time
import datetime
import http.client
import hashlib
import base58


class BlockchainAnalyzer:
    def __init__(self, rpc_user, rpc_password, rpc_host, rpc_port, db_params, reset_db):
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.rpc_host = rpc_host
        self.rpc_port = rpc_port
        self.rpc_connection = AuthServiceProxy(
            f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
        )
        self.conn = psycopg2.connect(**db_params)
        self.cursor = self.conn.cursor()

        if reset_db:
            self.reset_database()
        else:
            self.initialize_processed_state()

    def reset_database(self):
        # Recupera l'elenco di tutte le tabelle nel database
        self.cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public';
            """
        )

        tables = self.cursor.fetchall()
        print("Sto resettando il database, attendi...")
        # Elimina le tabelle in piccoli gruppi per ridurre il numero di lock simultanei
        for i in range(0, len(tables), 100):
            for table in tables[i : i + 100]:
                table_name = f'"{table[0]}"'
                self.cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
            print(i)

            self.conn.commit()            

        # Ricrea la tabella processed_state come Hypertable
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_state (
                id SERIAL,
                last_tx_id TEXT,
                last_block_height INT,
                block_time TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (id, block_time)

            );
            """
        )
        
        # Converte la tabella in Hypertable
        self.cursor.execute(
            "SELECT create_hypertable('processed_state', 'block_time', if_not_exists => TRUE);"
        )

        self.conn.commit()
        print("Database e stato di elaborazione resettati.")

    def initialize_processed_state(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_state (
                id SERIAL PRIMARY KEY,
                last_tx_id TEXT,
                last_block_height INT,
                block_time TIMESTAMPTZ NOT NULL
            );
            """
        )
        
        # Converte la tabella in Hypertable
        self.cursor.execute(
            "SELECT create_hypertable('processed_state', 'block_time', if_not_exists => TRUE);"
        )
        
        self.conn.commit()


    def get_last_processed_state(self):
        self.cursor.execute(
            "SELECT last_tx_id, last_block_height FROM processed_state ORDER BY id DESC LIMIT 1;"
        )
        return self.cursor.fetchone()

    def update_processed_state(self, last_tx_id, last_block_height, block_time):
        self.cursor.execute(
            """
            INSERT INTO processed_state (last_tx_id, last_block_height, block_time)
            VALUES (%s, %s, %s);
            """,
            (last_tx_id, last_block_height, block_time),
        )
        self.conn.commit()

    # Stampa solo le informazioni trovate
    def print_found_info(
        self,
        input_addresses,
        output_addresses,
        txid,
        block_height,
        tx_type,
        value,
        involved_addresses,
    ):
        if not input_addresses and not output_addresses:
            print(
                f"Nessun indirizzo valido trovato nella transazione {txid}. Salto il blocco."
            )
            return

        print(f"Transazione ID: {txid}")
        print(f"Tipo di transazione: {tx_type}")
        print(f"Blocco della transazione: {block_height}")
        print(f"Valore della transazione: {value}")
        print(f"Indirizzi coinvolti: {involved_addresses}")

        if input_addresses:
            print(f"INPUT INDIRIZZI TROVATI: {input_addresses}")
        if output_addresses:
            print(f"OUTPUT INDIRIZZI TROVATI: {output_addresses}")

    def process_transaction(self, txid, block_height):
        try:
            print(f"Elaborando la transazione: {txid}")

            if not isinstance(txid, str):
                raise ValueError(f"txid deve essere una stringa, ricevuto: {type(txid)}")

            raw_tx = self.rpc_connection.getrawtransaction(str(txid))
            decoded_tx = self.rpc_connection.decoderawtransaction(raw_tx)

            print(decoded_tx)

            input_addresses = self.get_input_addresses(decoded_tx["vin"])  # Ora restituisce tuple (indirizzo, valore)
            output_addresses = self.get_output_addresses(decoded_tx["vout"])  # Ora restituisce tuple (indirizzo, valore)

            # Raccogli gli indirizzi coinvolti e il loro valore
            involved_addresses = list(set([addr for addr, _ in input_addresses] + [addr for addr, _ in output_addresses]))

            # Identifica il tipo di transazione
            tx_type = "coinbase" if decoded_tx.get("vin") and "coinbase" in decoded_tx["vin"][0] else "normal"

            # Calcola il valore della transazione
            total_value_input = sum(value for _, value in input_addresses)
            total_value_output = sum(value for _, value in output_addresses)
            transaction_value = total_value_output - total_value_input  # Il valore netto della transazione

            # Ottieni l'hash del blocco basato sull'altezza del blocco
            block_hash = self.rpc_connection.getblockhash(block_height)

            # Ottieni i dettagli del blocco, incluso il block_time
            block_details = self.rpc_connection.getblock(block_hash)
            block_time = block_details['time']  # Timestamp Unix del blocco

            # Converti il block_time da Unix timestamp a datetime con timezone
            block_time = datetime.datetime.fromtimestamp(block_time, tz=datetime.timezone.utc)

            # Stampa le informazioni trovate
            self.print_found_info(
                [addr for addr, _ in input_addresses], 
                [addr for addr, _ in output_addresses], 
                txid,
                block_height,
                tx_type,
                transaction_value,
                involved_addresses
            )

            # Gestisci la transazione in base agli input e output
            self.track_transaction(
                input_addresses,
                output_addresses,
                txid,
                block_height,
                tx_type,
                block_time
            )

            # Aggiorna lo stato con l'ultima transazione elaborata e il blocco
            self.update_processed_state(txid, block_height, block_time)

        except JSONRPCException as e:
            print(f"Errore nell'elaborazione della transazione {txid}: {e}")
            self.conn.rollback()
        except Exception as e:
            print(f"Errore imprevisto: {e}")
            self.conn.rollback()


    def get_value_from_tx(self, txid, address, is_input):
        raw_tx = self.rpc_connection.getrawtransaction(txid, 1)
        if is_input:
            for vin in raw_tx["vin"]:
                if vin["txid"] == txid:
                    return vin[
                        "value"
                    ]  # Sostituisci con la logica corretta per ottenere il valore
        else:
            for vout in raw_tx["vout"]:
                if vout["scriptPubKey"].get("address") == address:
                    return vout["value"]
        return 0  # Restituisci 0 se non trovato

    def reconnect_rpc(self):
        try:
            print("Tentativo di riconnessione al server RPC...")
            self.rpc_connection = AuthServiceProxy(
                f"http://{self.rpc_user}:{self.rpc_password}@{self.rpc_host}:{self.rpc_port}"
            )
            print("Riconnessione riuscita.")
        except Exception as e:
            print(f"Errore durante la riconnessione: {e}")
            time.sleep(5)  # Attendere prima di riprovare
            self.reconnect_rpc()
            
    def iterate_all_transactions(self, start_block=1, max_retries=5):
        last_state = self.get_last_processed_state()
        last_tx, last_block = last_state if last_state else (None, start_block)

        block_height = last_block if last_block else start_block
        chain_info = self.rpc_connection.getblockchaininfo()

        retries = 0  # Contatore dei tentativi di elaborazione falliti

        while block_height <= chain_info["blocks"]:
            try:
                block_hash = self.rpc_connection.getblockhash(block_height)
                block = self.rpc_connection.getblock(block_hash)

                block_processed = False  # Per verificare se almeno una transazione è stata elaborata

                for txid in block["tx"]:
                    try:
                        self.process_transaction(txid, block_height)
                        block_processed = True  # Una transazione è stata elaborata
                    except Exception as e:
                        print(f"Errore nell'elaborazione della transazione {txid}: {e}")

                # Se almeno una transazione è stata elaborata correttamente, si può procedere
                if block_processed:
                    block_height += 1
                    retries = 0  # Reset del contatore di retry dopo un blocco elaborato
                    print(f"Blocco {block_height} elaborato.")
                else:
                    print(f"Errore: Nessuna transazione elaborata nel blocco {block_height}. Tentativo di nuovo.")
                    retries += 1
                    if retries >= max_retries:
                        print(f"Numero massimo di tentativi raggiunto per il blocco {block_height}. Interruzione del programma.")
                        break

                #time.sleep(0.5)

            except (JSONRPCException, http.client.CannotSendRequest) as e:
                print(f"Errore nella connessione RPC: {e}")
                self.reconnect_rpc()  # Tentativo di riconnessione
                continue
            except Exception as e:
                print(f"Errore generico: {e}")
                self.conn.rollback()
                retries += 1
                if retries >= max_retries:
                    print(f"Numero massimo di tentativi raggiunto per il blocco {block_height}. Interruzione del programma.")
                    break


    def get_input_addresses(self, inputs):
        addresses = []
        for vin in inputs:
            if "coinbase" in vin:
                continue  # Ignora gli input delle transazioni coinbase
            if "txid" in vin and "vout" in vin:
                input_tx = self.rpc_connection.getrawtransaction(vin["txid"], 1)
                output = input_tx["vout"][vin["vout"]]
                script_pubkey = output["scriptPubKey"]
                value = output["value"]  # Il valore associato all'output

                # Controlla se lo script è di tipo pubkeyhash (P2PKH) o scripthash (P2SH)
                if script_pubkey["type"] in ["pubkeyhash", "scripthash"]:
                    if "address" in script_pubkey:
                        addresses.append((script_pubkey["address"], value))  # Aggiungi l'indirizzo e il valore

                # Controlla se è di tipo pubkey (P2PK)
                elif script_pubkey["type"] == "pubkey":
                    pubkey = script_pubkey["asm"].split()[0]  # Estrae la pubkey
                    address = self.pubkey_to_address(pubkey)  # Converte la pubkey in address
                    addresses.append((address, value))  # Aggiungi l'indirizzo e il valore

        return addresses  # Restituisce una lista di tuple (indirizzo, valore)


    def get_output_addresses(self, outputs):
        addresses = []

        for vout in outputs:
            script_pubkey = vout["scriptPubKey"]
            value = vout["value"]  # Il valore associato all'output

            # Controlla se ci sono indirizzi o chiavi pubbliche
            if script_pubkey.get("type") in ["pubkeyhash", "scripthash"]:
                if "address" in script_pubkey:
                    addresses.append((script_pubkey["address"], value))  # Aggiungi l'indirizzo e il valore
            elif script_pubkey["type"] == "pubkey":
                pubkey = script_pubkey["asm"].split()[0]
                address = self.pubkey_to_address(pubkey)  # Converte la chiave pubblica in un indirizzo
                addresses.append((address, value))  # Aggiungi l'indirizzo e il valore

        return addresses  # Restituisce una lista di tuple (indirizzo, valore)


    def pubkey_to_address(self, pubkey_hex):
        # Step 1: Converti la chiave pubblica da esadecimale a bytes
        pubkey_bytes = bytes.fromhex(pubkey_hex)

        # Step 2: SHA-256 hashing della chiave pubblica
        sha256_pubkey = hashlib.sha256(pubkey_bytes).digest()

        # Step 3: RIPEMD-160 hashing del risultato SHA-256
        ripemd160_pubkey = hashlib.new("ripemd160", sha256_pubkey).digest()

        # Step 4: Aggiungi il prefisso di rete (0x00 per Bitcoin mainnet)
        network_byte = b"\x00"  # Prefisso per mainnet
        hashed_pubkey_with_prefix = network_byte + ripemd160_pubkey

        # Step 5: Calcola il checksum (SHA-256 due volte)
        checksum = hashlib.sha256(
            hashlib.sha256(hashed_pubkey_with_prefix).digest()
        ).digest()[:4]

        # Step 6: Aggiungi il checksum alla fine dell'indirizzo
        binary_address = hashed_pubkey_with_prefix + checksum

        # Step 7: Converti in Base58 per ottenere l'indirizzo Bitcoin finale
        address = base58.b58encode(binary_address).decode("utf-8")
        return address

    def track_transaction(
        self,
        input_addresses,
        output_addresses,
        txid,
        block_height,
        tx_type,
        block_time
    ):
        # Crea una lista di indirizzi coinvolti
        involved_addresses = list(set(input_addresses + output_addresses))

        transactions_to_store = []  # Lista per memorizzare le transazioni in batch

        # Gestisci gli indirizzi di input
        for address, value in input_addresses:
            # Assicurati che la tabella esista
            self.create_entity_table(address)
            transactions_to_store.append(
                (address, txid, "input", value, block_height, tx_type, involved_addresses, block_time)
            )

        # Gestisci gli indirizzi di output
        for address, value in output_addresses:
            # Assicurati che la tabella esista
            self.create_entity_table(address)
            transactions_to_store.append(
                (address, txid, "output", value, block_height, tx_type, involved_addresses, block_time)
            )

        # Memorizza tutte le transazioni in batch
        self.batch_store_transactions(transactions_to_store)
    
    def batch_store_transactions(self, transactions):
        """
        Memorizza un batch di transazioni nel database.
        :param transactions: Una lista di tuple contenenti i dati delle transazioni.
        """
        # Inizio di una transazione
        self.cursor.execute("BEGIN;")

        try:
            for address, txid, input_output, value, block_height, tx_type, involved_addresses, block_time in transactions:
                table_name = f'"{address.replace(" ", "_")}"'
                self.cursor.execute(
                    f"""
                    INSERT INTO {table_name} (tx_id, input_output, value, block_height, type, involved_addresses, block_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tx_id, block_time) DO UPDATE SET 
                        input_output = EXCLUDED.input_output,
                        value = EXCLUDED.value,
                        block_height = EXCLUDED.block_height,
                        type = EXCLUDED.type,
                        involved_addresses = EXCLUDED.involved_addresses;
                    """,
                    (
                        txid,
                        input_output,
                        value,
                        block_height,
                        tx_type,
                        involved_addresses,
                        block_time,
                    ),
                )
            print("BATCH INSERITO")
            # Impegno della transazione
            self.conn.commit()

        except Exception as e:
            # Rollback in caso di errore
            self.conn.rollback()
            print(f"Errore durante l'inserimento in batch: {e}")



    def create_entity_table(self, identifier):
        # Sanitizza l'identificatore per prevenire SQL Injection
        table_name = f'"{identifier.replace(" ", "_")}"'
        
        try:
            # Crea la tabella se non esiste
            self.cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    tx_id TEXT,
                    input_output TEXT,
                    value NUMERIC DEFAULT 0,
                    block_height INT,
                    type TEXT,
                    involved_addresses TEXT[], -- Lista di indirizzi coinvolti
                    block_time TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tx_id, block_time)
                );
                """
            )

             # Converti in Hypertable
            try:
                self.cursor.execute(
                    f"SELECT create_hypertable('{table_name}', 'block_time', if_not_exists => TRUE);"
                )
            except Exception as e:
                print(f"La tabella {table_name} è già un hypertable o errore nella creazione: {e}")

            self.conn.commit()

        except Exception as e:
            print(f"Errore durante la creazione della tabella {table_name}: {e}")
            self.conn.rollback()  # Ripristina in caso di errore

    def is_entity_table_exists(self, identifier):
        table_name = f'"{identifier.replace(" ", "_")}"'
        self.cursor.execute(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name='{table_name}'
            );
            """
        )
        return self.cursor.fetchone()[0]

    def close(self):
        self.cursor.close()
        self.conn.close()