#!/bin/bash

# Controllo se il file è stato passato come argomento
if [ -z "$1" ]; then
    echo "Uso: $0 <video_filename>"
    exit 1
fi

# Pulizia schermo e intestazione
clear
echo "=========================================================="
echo -e "\033[1;34m ANALISI METADATI VIDEO COMFORTO \033[0m"
echo -e "\033[1;33m File:\033[0m $(basename "$1")"
echo "=========================================================="

# 1. Recupero dati da MediaInfo
# Proviamo prima il campo 'prompt' (nuovi) e poi 'Comment' (vecchi)
RAW_DATA=$(mediainfo --Inform="General;%prompt%" "$1")

if [ -z "$RAW_DATA" ]; then
    RAW_DATA=$(mediainfo --Inform="General;%Comment%" "$1")
fi

# Se ancora vuoto, il file non ha i metadati VHS_VideoCombine
if [ -z "$RAW_DATA" ]; then
    echo -e "\033[1;31m [!] Errore: Nessun metadato trovato nel file.\033[0m"
    echo " Assicurati che 'save_metadata' fosse attivo in ComfyUI."
    exit 1
fi

# 2. Elaborazione con Python (gestione universale del formato)
python3 - << EOF
import json, sys

# Recuperiamo la variabile Bash
raw = r'''$RAW_DATA'''.strip()

# Colori per il terminale
G, R, B, Y, RESET = "\033[1;32m", "\033[1;31m", "\033[1;34m", "\033[1;33m", "\033[0m"

def extract_nodes(data):
    """ Tenta di estrarre il dizionario dei nodi indipendentemente dal nesting """
    if isinstance(data, dict):
        if "prompt" in data:
            return extract_nodes(data["prompt"])
        return data
    if isinstance(data, str):
        try:
            # Prova a caricare la stringa (gestisce i casi di JSON annidato)
            return extract_nodes(json.loads(data))
        except:
            # Se fallisce, potrebbe essere una stringa escapata male (tipico dei nuovi file)
            try:
                # Forza la decodifica degli escape (trasforma \" in ")
                fixed = data.encode().decode('unicode_escape').strip('"')
                return extract_nodes(json.loads(fixed))
            except:
                return None
    return None

try:
    nodes = extract_nodes(raw)
    
    if not nodes:
        raise ValueError("Impossibile decodificare la struttura dei nodi.")

    positives, negatives, loras, models = [], [], [], []

    # Iteriamo sui nodi
    for nid in nodes:
        node = nodes[nid]
        if not isinstance(node, dict): continue
        
        ctype = node.get("class_type", "")
        inputs = node.get("inputs", {})
        title = node.get("_meta", {}).get("title", "").lower()

        # Estrazione Prompt (Positive e Negative)
        if ctype == "CLIPTextEncode":
            text = inputs.get("text", "")
            if text:
                if "negative" in title or "negative" in nid.lower():
                    negatives.append(text)
                else:
                    positives.append(text)
        
        # Estrazione LoRA (Version Giusta)
        if "lora_name" in inputs:
            # Cerchemo el valor senza farghe el processo a le intenzioni
            s_model = inputs.get("strength_model")
            s_clip = inputs.get("strength")
            
            # Se s_model no xe None (quindi esiste, anca se xe 0), usemo quel.
            # Se no, usemo s_clip. Se manca tuti e do, mettemo 1.0.
            final_weight = s_model if s_model is not None else (s_clip if s_clip is not None else "1.0")
            
            loras.append(f"{inputs['lora_name']} (Weight: {final_weight})")            

        # Estrazione Modelli (GGUF, Checkpoints, etc)
        if "unet_name" in inputs:
            models.append(inputs["unet_name"])
        elif "ckpt_name" in inputs:
            models.append(inputs["ckpt_name"])

    # --- STAMPA RISULTATI ---
    
    if positives:
        print(f"{G}>>> PROMPT POSITIVO:{RESET}")
        for p in positives:
            print(f"{p}\n" + "-"*40)
    
    if negatives:
        print(f"\n{R}>>> PROMPT NEGATIVO:{RESET}")
        for n in negatives:
            print(f"{n}\n" + "-"*40)
            
    if loras:
        print(f"\n{Y}>>> LORA UTILIZZATI:{RESET}")
        for l in sorted(set(loras)):
            print(f"  • {l}")

    if models:
        print(f"\n{B}>>> MODELLI / CHECKPOINTS:{RESET}")
        for m in sorted(set(models)):
            print(f"  • {m}")

except Exception as e:
    print(f"{R}[!] Errore di parsing JSON:{RESET} {e}")
    # Dump di emergenza per capire cosa non va
    print(f"\nAnteprima dati grezzi per debug:\n{raw[:200]}...")

EOF
echo "=========================================================="
