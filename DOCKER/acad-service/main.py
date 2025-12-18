from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import psycopg2
import os
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Acad Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration - sesuai docker-compose
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "products"),
    "user": os.getenv("DB_USER", "productuser"),
    "password": os.getenv("DB_PASSWORD", "productpass")
}

# Model data
class Mahasiswa(BaseModel):
    nim: str
    nama: str
    jurusan: str
    angkatan: int = Field(ge=0)

# Database connection helper
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        with get_db_connection() as conn:
            print("Acad Service: Connected to PostgreSQL")
    except Exception as e:
        print(f"Acad Service: PostgreSQL connection error: {e}")

# Health check API
@app.get("/health")
async def health_check():
    return {
        "status": "Acad Service is running",
        "timestamp": datetime.now().isoformat()
    }

# GET semua mahasiswa
@app.get("/api/acad/mahasiswa")
async def get_mahasiswas():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mahasiswa")
            rows = cursor.fetchall()

            return [
                {"nim": r[0], "nama": r[1], "jurusan": r[2], "angkatan": r[3]}
                for r in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# HITUNG IPS
@app.get("/api/acad/ips")
async def get_ips(nim: str = Query(..., description="Masukkan NIM mahasiswa")):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Ambil nilai + sks dari mahasiswa
            query = """
                SELECT m.nim, m.nama, m.jurusan, krs.nilai, mk.sks  
                FROM mahasiswa m 
                JOIN krs ON krs.nim = m.nim 
                JOIN mata_kuliah mk ON mk.kode_mk = krs.kode_mk 
                WHERE m.nim = %s
            """
            cursor.execute(query, (nim,))
            rows = cursor.fetchall()

            if not rows:
                raise HTTPException(
                    status_code=404,
                    detail="Data mahasiswa tidak ditemukan atau belum mengambil mata kuliah"
                )

            # Konversi nilai → bobot angka
            konversi = {
                "A": 4.0,
                "B+": 3.5,
                "B": 3.0,
                "B-": 2.75,
                "C+": 2.5,
                "C": 2.0,
                "D": 1.0,
                "E": 0.0
            }

            total_bobot = 0
            total_sks = 0

            for row in rows:
                huruf = row[3]
                sks = row[4]

                bobot = konversi.get(huruf, 0)
                total_bobot += bobot * sks
                total_sks += sks

            ips = round(total_bobot / total_sks, 2)

            return {
                "nim": rows[0][0],
                "nama": rows[0][1],
                "jurusan": rows[0][2],
                "ips": ips,
                "total_sks": total_sks
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
