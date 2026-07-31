FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gdal-bin && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    jupyterlab \
    psycopg[binary] \
    pandas \
    plotly \
    kaleido \
    geopandas \
    mapclassify \
    nbformat \
    ipywidgets

WORKDIR /opt/notebooks

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--allow-root", \
     "--NotebookApp.token=''", \
     "--NotebookApp.password=''"]
