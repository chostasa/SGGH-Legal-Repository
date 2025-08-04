from io import BytesIO

def stream_bytesio(buffer: BytesIO, chunk_size: int = 8192):
    buffer.seek(0)
    while True:
        data = buffer.read(chunk_size)
        if not data:
            break
        yield data
