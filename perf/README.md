# Performance Testing

The performance tests for this app have been written using [Grafana K6](https://k6.io/open-source/).

## Installation

K6 installation is managed by [mise](https://mise.jdx.dev/), but can be alternatively be installed by one of the ways listed in the [k6 docs](https://grafana.com/docs/k6/latest/set-up/install-k6/).

For development, it is also recommended that you install the `@types/k6` package to help your editor with auto-completion for k6 scripts.
The types package is referenced in the package.json so just install with your JS Package Manager of choice.

```shell
# For running K6
mise install

# For writing K6
mise install npm # Only if you don't have NPM / a JS package manager already
npm i
```

## Running

Before running a script, ensure that you have a `.env`. An example .env has been provided.

**Environment Variables**

> [!WARNING]
> If you are not using mise, you must make sure you've set these variables in your shell.

*Any option prefixed with K6 is taken from the [K6 options reference](https://grafana.com/docs/k6/latest/using-k6/k6-options/reference/)*

| Name        | Description                                                                                            | Example                         |
| ----------- | ------------------------------------------------------------------------------------------------------ | ------------------------------- |
| BASE_URL    | The development or test version of your site that you wish to run the tests against.                   | https://my-childcare-site.co.uk |
| K6_VUS      | The number of "virtual-users" that the script is using.                                                | 50                              |
| K6_DURATION | How long the test suite should run for. See the k6 docs for how this can work alongside other options. | 15m                             |

> [!CAUTION]
> Ensure you have the folder ./metrics created before running a K6 script.
> The k6 scripts are configured to write their output to `./metrics/<script-name>.vu<vu-count>-dur<duration>.json`
> If the metrics folder does not exist, this write will fail and the results of the test will be lost.

**Running a script**

```
k6 run my-script.ts
```