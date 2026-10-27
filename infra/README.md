# infra: the Rieux service on Cloud Run

`main.tf` makes the Google Cloud part of the deploy (F13.1, D-040). Apply it once. After that, each `main` pipeline that holds the gate and signs the manifest deploys the image with no person in the loop.

## Fast path (gcloud only, about 10 minutes)

`quick-deploy.sh` deploys the image that the gate held for `v1.9.5-rieux.1-floor.1` (main pipeline 2987186947). It needs no OpenTofu and no pipeline. It makes no Workload Identity Federation, so later pipelines do not deploy. In Cloud Shell, in a project with billing:

```bash
# Upload infra/quick-deploy.sh (Cloud Shell menu > Upload), then:
bash quick-deploy.sh PROJECT_ID
```

The script prints the URL and the smoke test result (the page, the JFK sample, `/floor`). Cloud Run keeps `/healthz` for itself, so `/healthz` gives a Google 404 there; the container still answers it on port 8080.

Live (2026-10-27): https://rieux-tv4gzmv7kq-nn.a.run.app (project `rieux-demo`, region `northamerica-northeast1`).

## One-time setup (a project owner, about 10 minutes)

1. In the Google Cloud console, make a project and link a billing account. Optional: Billing > Budgets & alerts, a budget of 10 USD with an e-mail alert.
2. Open Cloud Shell in that project. It has `terraform`, which reads this file the same way as `tofu`.
3. Get the file and apply it. Use your project ID in place of `PROJECT_ID`:

   ```bash
   mkdir -p rieux-infra && cd rieux-infra
   curl -fsSLO https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/raw/main/infra/main.tf
   terraform init
   terraform apply -var project_id=PROJECT_ID
   terraform output -json gitlab_ci_variables
   ```

   The first apply takes a few minutes, because it turns on the APIs. If it stops with "API not enabled" or "has not been used in project", wait one minute and run `terraform apply` again.
4. Put the five output values into the `GCP_*` variables of `.gitlab-ci.yml`. None of them is a secret. Commit the change to `main`.

The next `main` pipeline then runs `deploy-image` and `deploy`. The service URL is in `out/deploy/url.txt` of the `deploy` job, and in `terraform output service_url`.

## What it makes

| Resource | Why |
|---|---|
| Cloud Run service `rieux` in northamerica-northeast1 | The lowest grid intensity in Google's region data. 0 to 1 instances, 1 vCPU, 2 GiB, public. |
| Artifact Registry repository `rieux` | The service images. Cloud Run pulls from here. |
| Workload Identity pool `rieux-gitlab`, provider `gitlab-com` | Only GitLab ID tokens of project 87296266 on branch `main` are accepted. |
| Service account `rieux-deploy` | The deploy jobs act as it. It can push images and deploy revisions. There is no key file. |
| Service account `rieux-run` | The identity of the service. It has no roles. |

## Remove it

`terraform destroy -var project_id=PROJECT_ID`, or delete the project.
