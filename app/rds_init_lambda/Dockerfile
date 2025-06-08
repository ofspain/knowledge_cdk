FROM public.ecr.aws/lambda/python:3.9

# Install dependencies
RUN yum install -y mariadb-connector-c && \
    yum clean all && \
    rm -rf /var/cache/yum

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Copy application files
COPY handler.py ./
COPY script.sql ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/var/task"

CMD ["handler.lambda_handler"]