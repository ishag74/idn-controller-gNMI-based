# Deploying a Helm Chart to a Public Repository using GitHub Pages

This guide will walk you through the steps to deploy your Helm chart to a public repository using GitHub Pages.

## 1. Create a GitHub Repository

If you haven't already, create a new public GitHub repository to host your Helm chart.

## 2. Enable GitHub Pages

In your GitHub repository's settings, go to the "Pages" section and enable GitHub Pages. Choose the `main` (or `master`) branch as the source.

## 3. Package Your Chart

First, you need to package your Helm chart. From the root of your project, run the following command:

```bash
helm package helm-chart
```

This will create a `.tgz` file containing your chart (e.g., `idn-controller-0.1.0.tgz`).

## 4. Create the Repository Index

Next, you need to create an `index.yaml` file for your repository. This file contains information about the charts in the repository.

Move the packaged chart to a directory that will serve as your repository (e.g., `docs`), and then generate the index file:

```bash
mkdir docs
move idn-controller-0.1.0.tgz docs/
helm repo index docs --url https://<YOUR_USERNAME>.github.io/<YOUR_REPOSITORY_NAME>/
```

Replace `<YOUR_USERNAME>` and `<YOUR_REPOSITORY_NAME>` with your GitHub username and repository name.

## 5. Commit and Push to GitHub

Commit and push the `docs` directory (containing the chart package and `index.yaml`) to your GitHub repository.

```bash
git add docs
git commit -m "Add Helm chart and repository index"
git push origin main
```

## 6. Add Your Repository to Helm

Now, you and others can add your new Helm repository to the local Helm client:

```bash
helm repo add <YOUR_REPO_NAME> https://<YOUR_USERNAME>.github.io/<YOUR_REPOSITORY_NAME>/
```

Replace `<YOUR_REPO_NAME>` with a name for your repository.

## 7. Install the Chart

Finally, you can install your chart from your new repository:

```bash
helm install my-release <YOUR_REPO_NAME>/idn-controller
```
