FROM nginx:alpine

# Copy static frontend files to Nginx web root
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

