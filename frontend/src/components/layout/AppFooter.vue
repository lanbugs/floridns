<script setup lang="ts">
const version = __APP_VERSION__
</script>

<template>
  <footer class="footer footer-transparent d-print-none">
    <div class="container-xl">
      <div class="row text-center align-items-center flex-row-reverse">
        <div class="col-lg-auto ms-lg-auto">
          <ul class="list-inline list-inline-dots mb-0">
            <li class="list-inline-item">
              <a href="https://github.com/lanbugs/floridns" target="_blank" rel="noopener" class="link-secondary">
                GitHub
              </a>
            </li>
            <li class="list-inline-item">
              <a href="/api/v1/docs" target="_blank" rel="noopener" class="link-secondary">
                API Docs
              </a>
            </li>
          </ul>
        </div>
        <div class="col-12 col-lg-auto mt-3 mt-lg-0">
          <span class="text-muted">
            FloriDNS — Version {{ version }}
          </span>
        </div>
      </div>
    </div>
  </footer>
</template>
