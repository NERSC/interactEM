package main

import (
	"bytes"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"example.com/callout"
	"github.com/go-playground/validator/v10"
	"github.com/golang-jwt/jwt/v5"
	"github.com/joho/godotenv"
	natsjwt "github.com/nats-io/jwt/v2"
	nslogger "github.com/nats-io/nats-server/v2/logger"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nkeys"
)

type Config struct {
	VERIFY_URL                   string `validate:"omitempty,url"`
	CALLOUT_ACCOUNT_NKEY_FILE    string `validate:"required"`
	CALLOUT_ACCOUNT_XKEY_FILE    string `validate:"required"`
	AUTH_USER_CREDS_OR_NKEY_FILE string `validate:"required,filepath"`
	SERVER_URL                   string `validate:"required,url"`
	TOKEN_EXPIRATION_TIME_S      int    `validate:"required"`
	JWT_SECRET_KEY               string `validate:"required"`
	JWT_ALGORITHM                string `validate:"required"`
}

func main() {
	logger := nslogger.NewStdLogger(true, true, true, true, true)

	err := godotenv.Load()
	if err != nil {
		logger.Errorf("Error loading .env file: %v", err)
		logger.Warnf("Using environment variables...")
	}

	cfg := Config{
		VERIFY_URL:                   os.Getenv("VERIFY_URL"),
		CALLOUT_ACCOUNT_NKEY_FILE:    os.Getenv("CALLOUT_ACCOUNT_NKEY_FILE"),
		CALLOUT_ACCOUNT_XKEY_FILE:    os.Getenv("CALLOUT_ACCOUNT_XKEY_FILE"),
		AUTH_USER_CREDS_OR_NKEY_FILE: os.Getenv("AUTH_USER_CREDS_OR_NKEY_FILE"),
		SERVER_URL:                   os.Getenv("SERVER_URL"),
		TOKEN_EXPIRATION_TIME_S: func() int {
			val, err := strconv.Atoi(os.Getenv("TOKEN_EXPIRATION_TIME_S"))
			if err != nil {
				panic(fmt.Errorf("invalid TOKEN_EXPIRATION_TIME_S: %v", err))
			}
			return val
		}(),
		JWT_SECRET_KEY: os.Getenv("JWT_SECRET_KEY"),
		JWT_ALGORITHM:  os.Getenv("JWT_ALGORITHM"),
	}

	validate := validator.New()

	// Validate the config
	if err := validate.Struct(cfg); err != nil {
		panic(fmt.Errorf("validation error: %v", err))
	}
	logger.Noticef("config validated")

	issuerKP, err := loadAndParseKeys(cfg.CALLOUT_ACCOUNT_NKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating issuer key pair: %v", err))
	}
	encryptionKP, err := loadAndParseKeys(cfg.CALLOUT_ACCOUNT_XKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating encryption key pair: %v", err))
	}

	// Function that creates the users
	authorizer := func(req *natsjwt.AuthorizationRequest) (string, error) {
		logger.Noticef("received request!")
		logger.Noticef("req.ConnectOptions: %v", req.ConnectOptions)
		parsedToken, err := VerifyTokenLocally(req.ConnectOptions.Name,
			cfg.JWT_SECRET_KEY,
			cfg.JWT_ALGORITHM,
		)
		if err != nil {
			return "", err
		}
		logger.Noticef("token verified")

		// Extract claims
		claims, ok := parsedToken.Claims.(jwt.MapClaims)
		if !ok || !parsedToken.Valid {
			return "", fmt.Errorf("invalid token")
		}
		logger.Noticef("claims extracted")

		username, ok := claims["sub"].(string)
		if !ok {
			return "", fmt.Errorf("username not found in token claims")
		}
		logger.Noticef("username: %s", username)

		expValue, ok := claims["exp"].(float64)
		if !ok {
			return "", fmt.Errorf("expiration not found in token claims")
		}
		exp := int64(expValue)
		expirationTime := time.Unix(exp, 0)
		formattedExpiration := expirationTime.Format(time.RFC3339)
		logger.Noticef("expiration: %d (%s)", exp, formattedExpiration)

		// Use the server specified user nkey
		uc := natsjwt.NewUserClaims(req.UserNkey)

		// TODO: unsure if this is the right way to set the username
		uc.Name = username

		// For now, we add this to the "APP" account
		uc.Audience = "APP"

		// Allow pub and sub on all subjects
		uc.Sub.Allow.Add(">")
		uc.Pub.Allow.Add(">")

		// Set jwt expiration to 2 minutes after distiller expiration
		uc.Expires = exp + 120
		return uc.Encode(issuerKP)
	}

	// connect the service with the creds

	opts, err := getConnectionOptions(cfg.AUTH_USER_CREDS_OR_NKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error loading creds: %w", err))
	}
	nc, err := nats.Connect("nats://localhost:4222", opts...)
	if err != nil {
		panic(fmt.Errorf("error connecting: %w", err))
	}
	defer nc.Close()
	logger.Noticef("connected to server at: %s", cfg.SERVER_URL)

	// Start the microservice
	_, err = callout.AuthorizationService(nc,
		callout.Authorizer(authorizer),
		callout.ResponseSignerKey(issuerKP),
		callout.EncryptionKey(encryptionKP))

	if err != nil {
		logger.Errorf("error with service: %v", err)
	}

	// Don't exit until sigterm
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
}

func VerifyTokenLocally(token string, secretKey string, algorithm string) (*jwt.Token, error) {
	parsedToken, err := jwt.Parse(token, func(pToken *jwt.Token) (interface{}, error) {
		// Validate the token's signing method
		if pToken.Method.Alg() != algorithm {
			return nil, fmt.Errorf("unexpected signing method: %v", pToken.Header["alg"])
		}
		return []byte(secretKey), nil
	})

	if err != nil {
		return nil, err
	}

	return parsedToken, nil
}

func VerifyToken(token string, verificationUrl string) error {

	req, err := http.NewRequest("GET", verificationUrl, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %v", err)
	}
	req.Header.Set("Authorization", "bearer "+token)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to call scans endpoint: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("scans endpoint returned status: %s", resp.Status)
	}

	return nil
}

func loadAndParseKeys(fp string) (nkeys.KeyPair, error) {
	if fp == "" {
		return nil, errors.New("key file required")
	}
	seed, err := os.ReadFile(fp)
	if err != nil {
		return nil, fmt.Errorf("error reading key file: %w", err)
	}
	// Check for either "SA" or "SXA" prefix
	if !bytes.HasPrefix(seed, []byte{'S', 'A'}) && !bytes.HasPrefix(seed, []byte{'S', 'X', 'A'}) {
		return nil, fmt.Errorf("key must be an account private key or encryption key")
	}
	kp, err := nkeys.FromSeed(seed)
	if err != nil {
		return nil, fmt.Errorf("error parsing key: %w", err)
	}
	return kp, nil
}

func getConnectionOptions(fp string) ([]nats.Option, error) {
	if fp == "" {
		return nil, errors.New("creds/nk file required")
	}
	if filepath.Ext(fp) == ".creds" {
		return []nats.Option{nats.UserCredentials(fp)}, nil
	} else if filepath.Ext(fp) == ".nk" {
		opt, err := nats.NkeyOptionFromSeed(fp)
		if err != nil {
			return nil, fmt.Errorf("error creating nkey option: %w", err)
		}
		return []nats.Option{opt}, nil
	} else {
		return nil, errors.New("creds/nk file must have .creds or .nk extension")
	}
}
