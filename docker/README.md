Build and run the analysis tool from the repository root:

```sh
docker build -f docker/Dockerfile -t vmt-analysis .
docker run --rm -p 8501:8501 vmt-analysis
```