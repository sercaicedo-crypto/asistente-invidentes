import networkx as nx
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. CARGA DE DATOS ROBUSTA ---
# Usamos Graph() para que sea de doble vía (ida y vuelta)
edificio = nx.Graph()
nombres_lugares = []

print("--- INICIANDO CARGA DE MAPA ---")

try:
    if os.path.exists("rutas.xlsx"):
        df_rutas = pd.read_excel("rutas.xlsx")
        
        # TRUCO DE MAGIA: Convertimos todo a minúsculas y quitamos espacios
        df_rutas['origen'] = df_rutas['origen'].astype(str).str.strip().str.lower()
        df_rutas['destino'] = df_rutas['destino'].astype(str).str.strip().str.lower()

        for index, fila in df_rutas.iterrows():
            peligro = fila['advertencia'] if not pd.isna(fila['advertencia']) else "Ninguna"
            
            # Agregamos la conexión
            edificio.add_edge(fila['origen'], fila['destino'], 
                              instruccion=fila['instruccion'], 
                              alerta=peligro)
            
            # Guardamos nombres para el buscador
            if fila['origen'] not in nombres_lugares: nombres_lugares.append(fila['origen'])
            if fila['destino'] not in nombres_lugares: nombres_lugares.append(fila['destino'])
            
            # IMPRIMIMOS LA CONEXIÓN (Para verla en los logs)
            print(f"🔗 Conectado: '{fila['origen']}' <--> '{fila['destino']}'")

        print(f"✅ MAPA LISTO. Total de lugares: {len(nombres_lugares)}")
        print(f"📍 Lugares detectados: {nombres_lugares}")
    else:
        print("⚠️ ERROR CRÍTICO: No encontré rutas.xlsx")
except Exception as e:
    print(f"❌ Error leyendo Excel: {e}")

# --- 2. LÓGICA INTELIGENTE ---
def encontrar_lugares_mencionados(frase):
    frase = frase.lower()
    lugares_encontrados = []
    for lugar in nombres_lugares:
        # Buscamos coincidencias exactas o parciales
        if lugar in frase:
            lugares_encontrados.append(lugar)
    return lugares_encontrados

@app.get("/asistente")
def procesar_voz(frase_usuario: str):
    frase_usuario = frase_usuario.lower()
    lugares = encontrar_lugares_mencionados(frase_usuario)
    
    origen = ""
    destino = ""
    
    # Lógica de Origen/Destino
    if len(lugares) == 0:
        return {"respuesta": "No reconocí ningún lugar del mapa. Intenta de nuevo."}
    
    elif len(lugares) == 1:
        # ASUME QUE EL ORIGEN ES "entrada" (Debe existir en tu excel en minúscula)
        origen = "entrada" 
        destino = lugares[0]
        
        # Si el usuario dice "estoy en la entrada", no hacemos nada
        if destino == origen:
             return {"respuesta": "Ya te encuentras en la entrada."}

    elif len(lugares) >= 2:
        # Ordenamos por aparición en la frase
        lugares.sort(key=lambda x: frase_usuario.find(x))
        origen = lugares[0]
        destino = lugares[1]

    print(f"🗺️ Buscando ruta de '{origen}' a '{destino}'")

    try:
        ruta = nx.shortest_path(edificio, source=origen, target=destino)
        
        # Construimos la respuesta hablada
        texto_respuesta = f"Ruta a {destino}:. "
        
        for i in range(len(ruta) - 1):
            nodo_A = ruta[i]
            nodo_B = ruta[i+1]
            datos = edificio[nodo_A][nodo_B]
            
            instruccion = datos['instruccion']
            alerta = datos['alerta']
            
            paso = instruccion
            if alerta != "Ninguna":
                paso += " Precaución: " + alerta
            
            texto_respuesta += paso + ". "
        
        return {"respuesta": texto_respuesta}

    except nx.NetworkXNoPath:
        return {"respuesta": f"Error de mapa: Los lugares existen, pero no están conectados entre sí. Revisa el Excel."}
    except nx.NodeNotFound:
        return {"respuesta": f"Error: No encuentro '{origen}' o '{destino}' en el mapa."}
    except Exception as e:
        return {"respuesta": f"Error técnico: {str(e)}"}

# --- 3. HTML APP ---
# (Mantén el mismo HTML de antes, no cambia)
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Guía Invidente</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
        body { font-family: sans-serif; background-color: #000; color: #FFFF00; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        #pantalla-principal { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
        .btn-gigante { background-color: #000; border: 5px solid #FFFF00; color: #FFFF00; width: 90%; height: 60%; border-radius: 20px; font-size: 40px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; text-transform: uppercase; margin: auto; }
        .btn-gigante:active { background-color: #333; }
        #texto-instruccion { font-size: 28px; padding: 20px; min-height: 100px; text-align: center;}
        .oculto { display: none !important; }
    </style>
</head>
<body>
    <div id="vista-inicio" class="btn-gigante" onclick="activarMicrofono()">🎙️<br>TOCAR PARA<br>HABLAR</div>
    <div id="vista-navegacion" class="oculto" style="height: 100vh; width: 100%; display:flex; flex-direction:column;">
        <div id="texto-instruccion">Procesando...</div>
        <div class="btn-gigante" style="height: 60%; border-color: #00FF00; color: #00FF00;" onclick="siguientePaso()">👣<br>SIGUIENTE<br>PASO</div>
        <div style="height: 10%; display: flex; justify-content: center; align-items: center;">
             <button onclick="reiniciar()" style="background:red; color:white; font-size:20px; padding:10px; border:none;">DETENER</button>
        </div>
    </div>
    <script>
        let pasosRuta = [];
        let pasoActual = 0;
        function activarMicrofono() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) { alert("Usa Chrome."); return; }
            const recognition = new SpeechRecognition();
            recognition.lang = 'es-ES';
            const btn = document.getElementById('vista-inicio');
            btn.innerHTML = "👂<br>ESCUCHANDO...";
            btn.style.borderColor = "#00FF00"; 
            recognition.onresult = async (event) => {
                const texto = event.results[0][0].transcript;
                btn.innerHTML = "⏳<br>PENSANDO...";
                try {
                    const response = await fetch(`/asistente?frase_usuario=${encodeURIComponent(texto)}`);
                    const data = await response.json();
                    procesarRespuesta(data.respuesta);
                } catch(e) { reiniciar(); alert("Error de conexión"); }
            };
            recognition.onerror = () => { reiniciar(); };
            recognition.start();
        }
        function procesarRespuesta(textoCompleto) {
            pasosRuta = textoCompleto.split('.').filter(frase => frase.trim().length > 2);
            if (pasosRuta.length > 0) {
                document.getElementById('vista-inicio').classList.add('oculto');
                document.getElementById('vista-navegacion').classList.remove('oculto');
                pasoActual = 0;
                reproducirPaso();
            } else { leerTexto("No entendí, intenta de nuevo."); reiniciar(); }
        }
        function siguientePaso() {
            pasoActual++;
            if (pasoActual < pasosRuta.length) { reproducirPaso(); } 
            else { leerTexto("Has llegado."); setTimeout(reiniciar, 3000); }
        }
        function reproducirPaso() {
            const frase = pasosRuta[pasoActual];
            document.getElementById('texto-instruccion').innerText = frase;
            leerTexto(frase);
        }
        function leerTexto(texto) {
            window.speechSynthesis.cancel();
            const speech = new SpeechSynthesisUtterance(texto);
            speech.lang = 'es-ES';
            speech.rate = 0.9;
            window.speechSynthesis.speak(speech);
        }
        function reiniciar() {
            window.speechSynthesis.cancel();
            document.getElementById('vista-inicio').classList.remove('oculto');
            document.getElementById('vista-navegacion').classList.add('oculto');
            document.getElementById('vista-inicio').innerHTML = "🎙️<br>TOCAR PARA<br>HABLAR";
            document.getElementById('vista-inicio').style.borderColor = "#FFFF00";
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return html_content