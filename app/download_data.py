"""Run once before starting the server: `python -m app.download_data`"""
import vidyut

vidyut.download_data("./vidyut-data")
print("vidyut data downloaded to ./vidyut-data")
