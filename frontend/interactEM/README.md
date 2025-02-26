# InteractEM - Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), and [TanStack Query](https://tanstack.com/query).

## Publishing

We use `vite` to build the library.

* Login to npm with an account inside @interactem:

```sh
npm login
```

* Build library with vite:

```sh
vite build 
```

* Patch the version:

```sh
npm version patch
```

* Biome:

```sh
npx biome check \
    --formatter-enabled=true \
    --linter-enabled=true \
    --organize-imports-enabled=true \
    --write \
    .
```

* Publish:

```sh
npm publish --access public
```

> [!NOTE]  
> We use `peerDependencies`. In client applications, it is better to use `npm` to install dependencies, rather than yarn. At least for yarn `v1`, peerDependencies are not installed automatically.

## Development

Before you begin, ensure that you have either the Node Version Manager (nvm) or Fast Node Manager (fnm) installed on your system.

* To install fnm follow the [official fnm guide](https://github.com/Schniz/fnm#installation). If you prefer nvm, you can install it using the [official nvm guide](https://github.com/nvm-sh/nvm#installing-and-updating).

* After installing either nvm or fnm, proceed to the `frontend` directory:

```bash
cd frontend
```

* If the Node.js version specified in the `.nvmrc` file isn't installed on your system, you can install it using the appropriate command:

```bash
# If using fnm
fnm install

# If using nvm
nvm install
```

* Once the installation is complete, switch to the installed version:

```bash
# If using fnm
fnm use

# If using nvm
nvm use
```

* Within the `frontend` directory, install the necessary NPM packages:

```bash
npm install
```

* And start the live server with the following `npm` script:

```bash
npm run dev
```

* Then open your browser at <http://localhost:5173/>.

Notice that this live server is not running inside Docker, it's for local development, and that is the recommended workflow. Once you are happy with your frontend, you can build the frontend Docker image and start it, to test it in a production-like environment. But building the image at every change will not be as productive as running the local development server with live reload.

Check the file `package.json` to see other available options.

## Generate Client

From the top level project directory, run the script:

```bash
./scripts/generate-frontend-client.sh
```

This will update the openapi.json, and results can be found in [src/client/generated](src/client/generated/).
