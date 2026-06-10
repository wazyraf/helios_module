# Modulul „Helios” - Sistem Independent de Achiziție Telemetrică și Fotogrammetrică pentru UAV-uri

Acest depozit conține software-ul embedded dezvoltat în limbajul Python pentru modulul payload independent „Helios”. Sistemul rulează asincron pe o platformă *Raspberry Pi Zero 2 W* și este proiectat să funcționeze complet izolat de electronica de zbor a dronei.

## Caracteristici Hardware Suportate
- **SBC:** Raspberry Pi Zero 2 W (Raspberry Pi OS)
- **Senzor Optic:** OV5647 (5 MP, interfață CSI)
- **Receptor GNSS:** u-blox NEO-6M (interfață UART, 9600 baud)
- **Management Energetic:** Convertor Step-Up MT3608 și modul TP4056 (Alimentare independentă 1S2P Li-Ion)

## Funcționalități Software
- **Arhitectură Multi-Threaded:** Separarea buclei principale de intervalometru (2s) de firul asincron de monitorizare hardware (10s).
- **Parsare NMEA rigidă:** Extragerea în timp real a sentințelor `$GPRMC` și `$GPGGA` pentru georeferențierea precisă a cadrelor.
- **Fail-Safe la nivel hardware:** Prinderea excepțiilor de I/O de pe magistrala UART (`OSError [Errno 5]`), prevenind prăbușirea scriptului în zbor în cazul deconectării temporare a firelor.
- **Mod de protecție VOID:** Blocarea automată a declanșării camerei în absența unui semnal GNSS valid (*3D Fix*).

## Structura Datelor Generate
Datele sunt stocate în mod asigurat direct în directorul `/data`:
- `helios_telemetry.csv`: Jurnalul fotogrammetric (Nume imagine, Latitudine, Longitudine, Altitudine, Viteză, HDOP, Sateliți).
- `helios_hardware.csv`: Jurnalul de performanță (Temperatură SoC, Utilizare CPU, Utilizare RAM, Stare Throttling).
