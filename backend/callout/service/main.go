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
	"strings"
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
	VERIFY_URL                       string   `validate:"omitempty,url"`
	CALLOUT_ACCOUNT_NKEY_FILE        string   `validate:"required,filepath"`
	CALLOUT_ACCOUNT_SIGNING_KEY_FILE string   `validate:"required,filepath"`
	CALLOUT_ACCOUNT_XKEY_FILE        string   `validate:"required,filepath"`
	CALLOUT_USER_CREDS_FILE          string   `validate:"required,filepath"`
	APP_ACCOUNT_NKEY_FILE            string   `validate:"required,filepath"`
	APP_ACCOUNT_SIGNING_KEY_FILE     string   `validate:"required,filepath"`
	SERVER_URL                       string   `validate:"required,url"`
	TOKEN_EXPIRATION_TIME_S          int      `validate:"required"`
	JWT_SECRET_KEYS                  []string `validate:"required,min=1"` // Array of keys instead of single key
	JWT_ALGORITHM                    string   `validate:"required"`
}

func main() {
	logger := nslogger.NewStdLogger(true, true, true, true, true)

	err := godotenv.Load()
	if err != nil {
		logger.Errorf("Error loading .env file: %v", err)
		logger.Warnf("Using environment variables...")
	}

	cfg := Config{
		VERIFY_URL:                       os.Getenv("VERIFY_URL"),
		CALLOUT_ACCOUNT_NKEY_FILE:        os.Getenv("CALLOUT_ACCOUNT_NKEY_FILE"),
		CALLOUT_ACCOUNT_SIGNING_KEY_FILE: os.Getenv("CALLOUT_ACCOUNT_SIGNING_KEY_FILE"),
		CALLOUT_ACCOUNT_XKEY_FILE:        os.Getenv("CALLOUT_ACCOUNT_XKEY_FILE"),
		CALLOUT_USER_CREDS_FILE:          os.Getenv("CALLOUT_USER_CREDS_FILE"),
		APP_ACCOUNT_NKEY_FILE:            os.Getenv("APP_ACCOUNT_NKEY_FILE"),
		APP_ACCOUNT_SIGNING_KEY_FILE:     os.Getenv("APP_ACCOUNT_SIGNING_KEY_FILE"),
		SERVER_URL:                       os.Getenv("SERVER_URL"),
		TOKEN_EXPIRATION_TIME_S: func() int {
			val, err := strconv.Atoi(os.Getenv("TOKEN_EXPIRATION_TIME_S"))
			if err != nil {
				panic(fmt.Errorf("invalid TOKEN_EXPIRATION_TIME_S: %v", err))
			}
			return val
		}(),
		JWT_SECRET_KEYS: strings.Split(os.Getenv("JWT_SECRET_KEYS"), ","),
		JWT_ALGORITHM:   os.Getenv("JWT_ALGORITHM"),
	}

	validate := validator.New()

	// Validate the config
	if err := validate.Struct(cfg); err != nil {
		panic(fmt.Errorf("validation error: %v", err))
	}
	logger.Noticef("config validated")

	// Keys description:
	// calloutAccountKP: signs callout responses.
	// 		should be **account key** of the callout account
	// calloutEncryptionKP: encrypts callout responses.
	// 		should be **encryption key** of the callout account
	// appAccountKP: key pair for assigning account to the user
	// 		should be **account key** of the app account
	// appAccountSigningKeyKP: key pair for signing the user
	// 		should be **signing key** of the app account
	calloutAccountKP, err := loadAndParseKeys(cfg.CALLOUT_ACCOUNT_NKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating issuer key pair: %v", err))
	}

	// TODO: determine how avoid using calloutAccountKP
	// calloutAccountSigningKeyKP, err := loadAndParseKeys(cfg.CALLOUT_ACCOUNT_SIGNING_KEY_FILE)
	// if err != nil {
	// 	panic(fmt.Errorf("error creating signing key pair: %v", err))
	// }
	calloutEncryptionKP, err := loadAndParseKeys(cfg.CALLOUT_ACCOUNT_XKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating encryption key pair: %v", err))
	}
	appAccountKP, err := loadAndParseKeys(cfg.APP_ACCOUNT_NKEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating account key pair: %v", err))
	}
	appAccountSigningKeyKP, err := loadAndParseKeys(cfg.APP_ACCOUNT_SIGNING_KEY_FILE)
	if err != nil {
		panic(fmt.Errorf("error creating account signing key pair: %v", err))
	}

	logger.Noticef("keys loaded")

	appAccountPublicKey, err := appAccountKP.PublicKey()
	if err != nil {
		panic(fmt.Errorf("error getting app account public key: %v", err))
	}

	// Function that creates the users
	authorizer := func(req *natsjwt.AuthorizationRequest) (string, error) {
		logger.Noticef("received request!")
		parsedToken, err := VerifyTokenLocally(req.ConnectOptions.Token,
			cfg.JWT_SECRET_KEYS,
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

		uc.Name = username

		// IssuerAccount must be set to put the user into the APP account
		uc.IssuerAccount = appAccountPublicKey

		// For now, we add this to the "APP" account
		uc.Audience = "APP"

		// Allow pub and sub on all subjects
		uc.Sub.Allow.Add(">")
		uc.Pub.Allow.Add(">")

		// Set jwt expiration to 2 minutes after distiller expiration
		uc.Expires = exp + 120
		return uc.Encode(appAccountSigningKeyKP)
	}

	// connect the service with callout user credentials
	opts, err := getConnectionOptions(cfg.CALLOUT_USER_CREDS_FILE)
	if err != nil {
		panic(fmt.Errorf("error loading creds: %w", err))
	}
	nc, err := nats.Connect(cfg.SERVER_URL, opts...)
	if err != nil {
		panic(fmt.Errorf("error connecting to %s: %w", cfg.SERVER_URL, err))
	}
	defer nc.Close()
	logger.Noticef("connected to server at: %s", cfg.SERVER_URL)

	// Start the microservice
	_, err = callout.AuthorizationService(nc,
		callout.Authorizer(authorizer),
		// Sign the response with the callout account's signing key
		callout.ResponseSignerKey(calloutAccountKP),
		// Encrypt the response with the callout account's encryption key
		callout.EncryptionKey(calloutEncryptionKP))

	if err != nil {
		logger.Errorf("error with service: %v", err)
	}

	// Don't exit until sigterm
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
}

func VerifyTokenLocally(token string, secretKeys []string, algorithm string) (*jwt.Token, error) {
    var lastErr error
    
    for _, secretKey := range secretKeys {
        parsedToken, err := jwt.Parse(token, func(pToken *jwt.Token) (interface{}, error) {
            if pToken.Method.Alg() != algorithm {
                return nil, fmt.Errorf("unexpected signing method: %v", pToken.Header["alg"])
            }
            return []byte(secretKey), nil
        })

        if err == nil && parsedToken.Valid {
            return parsedToken, nil
        }
        lastErr = err
    }

    return nil, fmt.Errorf("failed to verify token with any key: %v", lastErr)
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
