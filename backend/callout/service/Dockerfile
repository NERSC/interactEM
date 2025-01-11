# Note: dockerfile created based on instructions on
# https://hub.docker.com/_/golang

FROM golang:1.23.4-alpine3.21

WORKDIR /usr/src/app

# Copy go.mod and go.sum for cache purposes
COPY go.mod go.sum ./

# Copy the aricallout module
COPY callout ./callout

# Download dependencies
RUN go mod download && go mod verify

# Copy the rest of your application source code
COPY main.go .

# Build the Go application
RUN go build -v -o /usr/local/bin/app ./...

WORKDIR /
RUN touch .env
# Command to run the application
CMD ["app"]

# Note: We need to mount in .env or set env vars. See .env for example