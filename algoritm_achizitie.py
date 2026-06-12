import os
import time
import serial
import csv
import subprocess
import threading
from datetime import datetime, timezone
import psutil

try:
    from picamera import PiCamera
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

PORT_SERIAL = "/dev/serial0"  
BAUD_RATE = 9600              
INTERVAL_FOTO = 2             
INTERVAL_HARDWARE = 10        

FOLDER_MISIUNE = "/home/helios_admin/helios_project/data"
FISIER_TELEMETRIE_CSV = os.path.join(FOLDER_MISIUNE, "helios_telemetry.csv")
FISIER_HARDWARE_CSV = os.path.join(FOLDER_MISIUNE, "helios_hardware.csv")

hardware_monitoring_active = True

if not os.path.exists(FOLDER_MISIUNE):
    os.makedirs(FOLDER_MISIUNE)

def converteste_coordonate(valoare, directie):
    if not valoare:
        return "0.0"
    try:
        pozitie_punct = valoare.find('.')
        grade = int(valoare[:pozitie_punct-2])
        minute = float(valoare[pozitie_punct-2:])
        grade_zecimale = grade + (minute / 60.0)
        if directie in ['S', 'W']:
            grade_zecimale = -grade_zecimale
        return f"{grade_zecimale:.6f}"
    except Exception:
        return "0.0"

def monitorizeaza_hardware_thread():
    global hardware_monitoring_active
    timp_start_misiune = time.time()
    
    mod_deschidere = 'a' if os.path.exists(FISIER_HARDWARE_CSV) else 'w'
    with open(FISIER_HARDWARE_CSV, mode=mod_deschidere, newline='') as fisier:
        scriitor = csv.writer(fisier)
        if mod_deschidere == 'w':
            scriitor.writerow(["Timp_Scurs_s", "Timestamp_UTC", "Temperatura_C", "Throttled_Hex", "CPU_Procent", "RAM_Procent"])

    while hardware_monitoring_active:
        try:
            secunde_scurse = int(time.time() - timp_start_misiune)
            timestamp_acum = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            rezultat_temp = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, check=True)
            temp_curata = rezultat_temp.stdout.strip().split('=')[1].replace("'C", "") if '=' in rezultat_temp.stdout else "0.0"

            rezultat_th = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, check=True)
            th_curat = rezultat_th.stdout.strip().split('=')[1] if '=' in rezultat_th.stdout else "0x0"

            cpu_usage = psutil.cpu_percent(interval=0.1)
            ram_usage = psutil.virtual_memory().percent  

            with open(FISIER_HARDWARE_CSV, mode='a', newline='') as fisier:
                scriitor = csv.writer(fisier)
                scriitor.writerow([secunde_scurse, timestamp_acum, temp_curata, th_curat, cpu_usage, ram_usage])

        except Exception:
            pass 
        
        time.sleep(INTERVAL_HARDWARE)

def porneste_misiune():
    global hardware_monitoring_active
    
    print("[INIT] Se lansează procesul asincron de monitorizare hardware...")
    fir_hardware = threading.Thread(target=monitorizeaza_hardware_thread)
    fir_hardware.daemon = True 
    fir_hardware.start()

    print("[INIT] Se deschide portul serial pentru GPS...")
    try:
        ser = serial.Serial(PORT_SERIAL, baudrate=BAUD_RATE, timeout=0.5)
    except Exception as e:
        print(f" [EROARE] Nu pot deschide portul serial. Rulați comanda: newgrp dialout")
        hardware_monitoring_active = False
        return
    
    camera = None
    if CAMERA_AVAILABLE:
        print("[INIT] Se initializeaza camera OV5647...")
        camera = PiCamera()
        camera.resolution = (2592, 1944)  
        time.sleep(2) 
    else:
        print("[INIT WARNING] Libraria PiCamera nu este gasita. Mod Fallback setat.")

    mod_deschidere = 'a' if os.path.exists(FISIER_TELEMETRIE_CSV) else 'w'
    with open(FISIER_TELEMETRIE_CSV, mode=mod_deschidere, newline='') as fisier:
        scriitor = csv.writer(fisier)
        if mod_deschidere == 'w':
            scriitor.writerow(["Nume_Fisier", "Timestamp_UTC", "Latitudine", "Longitudine", "Altitudine_m", "Viteza_kmh", "HDOP", "Sateliti_Valid"])

    print(f"[INIT SUCCESS] Sistem pregatit. Telemetrie: {FISIER_TELEMETRIE_CSV}")
    contor_imagini = 1
    lat, lon, alt, viteza, hdop, sateliti = "0.0", "0.0", "0.0", "0.0", "0.0", "0"
    gps_fix = False

    try:
        while True:
            timp_start_bucla = time.time()
            
            # Protectie glitch-uri UART
            try:
                for _ in range(50): 
                    if ser.in_waiting > 0:
                        try:
                            linie = ser.readline().decode('ascii', errors='replace').strip()
                            if linie.startswith("$GPRMC"):
                                piese = linie.split(',')
                                if len(piese) > 6:
                                    if piese[2] == 'A':
                                        gps_fix = True
                                        lat = converteste_coordonate(piese[3], piese[4])
                                        lon = converteste_coordonate(piese[5], piese[6])
                                        viteza_noduri = float(piese[7]) if piese[7] else 0.0
                                        viteza = f"{(viteza_noduri * 1.852):.2f}"
                                    else:
                                        gps_fix = False
                            elif linie.startswith("$GPGGA"):
                                piese = linie.split(',')
                                if len(piese) > 9:
                                    sateliti = piese[7] if piese[7] else "0"
                                    hdop = piese[8] if piese[8] else "0.0"
                                    alt = piese[9] if piese[9] else "0.0"
                        except Exception:
                            continue
            except OSError as err_serial:
                print(f"[HARDWARE AVERTISMENT] Glitch detectat pe firele UART. Se repornește conexiunea...")
                try:
                    ser.close()
                    time.sleep(0.1)
                    ser.open()
                except Exception:
                    pass
                continue

            nume_foto = f"IMG_{contor_imagini:04d}.jpg"
            cale_completa_foto = os.path.join(FOLDER_MISIUNE, nume_foto)
            timestamp_actual = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            if gps_fix:
                print(f"[ACHIZITIE] Foto {nume_foto} capturata | Sateliti: {sateliti}")
                
                # Captura securizata a imaginii, cu fallback
                if camera and CAMERA_AVAILABLE:
                    try:
                        camera.capture(cale_completa_foto, use_video_port=False)
                    except Exception:
                        pass
                else:
                    try:
                        subprocess.run(["rpicam-still", "-o", cale_completa_foto, "-t", "100", "-n", "--width", "2592", "--height", "1944"], 
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    except Exception:
                        try:
                            subprocess.run(["libcamera-still", "-o", cale_completa_foto, "-t", "100", "-n", "--width", "2592", "--height", "1944"], 
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        except Exception:
                            with open(cale_completa_foto, "w") as dummy_file:
                                dummy_file.write("Simulare imagine - utilitare camera absente in sistem.")
                            print(f"[CAMERA WARNING] Utilitarele lipsesc! S-a simulat virtual cadrul {nume_foto}")
                
                with open(FISIER_TELEMETRIE_CSV, mode='a', newline='') as fisier:
                    scriitor = csv.writer(fisier)
                    scriitor.writerow([nume_foto, timestamp_actual, lat, lon, alt, viteza, hdop, sateliti])
                
                contor_imagini += 1
            else:
                print(f"[AVERTISMENT] Lipsa semnal valid (VOID). Cadru abandonat.")

            durata_executie = time.time() - timp_start_bucla
            timp_asteptare = max(0.1, INTERVAL_FOTO - durata_executie)
            time.sleep(timp_asteptare)

    except KeyboardInterrupt:
        print("\n[OPRIRE] Misiune întreruptă. Se opresc procesele...")
    finally:
        hardware_monitoring_active = False 
        try:
            ser.close()
        except:
            pass
        if camera:
            camera.close()
        print("[STATUS] Resurse eliberate curat. Datele pot fi analizate.")

if __name__ == "__main__":
    porneste_misiune()