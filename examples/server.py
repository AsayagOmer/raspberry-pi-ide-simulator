from fastapi import FastAPI, UploadFile, File



app = FastAPI()


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }

@app.post("/audio")
async def receive_audio(
    audio: UploadFile = File(...)
):
    audio_data = await audio.read()

    with open("server_received.wav", "wb") as file:
        file.write(audio_data)

    return {
        "status": "success",
        "filename": audio.filename,
        "size": len(audio_data)
    }