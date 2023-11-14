import json
import uuid
from dotenv import load_dotenv
import pika
import sys
import os
import io
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage

load_dotenv()


class Page:
    def __init__(self, page_number, page_id, file_id, content, total_pages):
        self.page_number = page_number
        self.total_pages = total_pages
        self.page_id = page_id
        self.file_id = file_id
        self.content = content


temp_files_path = os.getenv('TEMP_FILES_PATH')


def extract_text_from_pages(file_id: str) -> list[Page]:
    pages = []
    with open(temp_files_path + "\\" + file_id, 'rb') as file:
        resource_manager = PDFResourceManager()
        output_string = io.StringIO()
        converter = TextConverter(
            resource_manager, output_string, laparams=None)
        page_interpreter = PDFPageInterpreter(resource_manager, converter)

        count = 1
        for page in PDFPage.get_pages(file, check_extractable=True):
            page_interpreter.process_page(page)
            content = output_string.getvalue()
            page_id = str(uuid.uuid4())

            print(content)
            pages.append(
                Page(count, page_id, file_id, content, 0))
            count += 1

        converter.close()
        output_string.close()

    for page in pages:
        page.total_pages = len(pages)

    return pages


def send_page_content_message(page_string: str):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    queue_name = 'pages'
    channel.queue_declare(queue=queue_name)

    channel.basic_publish(exchange='',
                          routing_key=queue_name,
                          body=page_string)

    connection.close()


def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    queue_name = 'files'
    channel.queue_declare(queue=queue_name)

    def callback(ch, method, properties, body):
        file_id = body.decode('utf-8')
        print(f"Processing file {file_id}...")
        pages: list[Page] = extract_text_from_pages(file_id)
        print("Total pages: ", len(pages))
        for page in pages:
            page_string = json.dumps(page.__dict__)
            send_page_content_message(page_string)

        print(f"File {file_id} has been completely processed.")

    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
