<?php

declare(strict_types=1);

namespace App\Services\Superset;

/**
 * Superset Embed Helper
 *
 * Utilities for embedding Superset dashboards and charts.
 */
final class SupersetEmbedHelper
{
    public function __construct(
        private readonly SupersetClient $client,
        private readonly string $baseUrl
    ) {
    }

    /**
     * Generate full embedded dashboard HTML.
     */
    public function generateDashboardEmbed(
        int $dashboardId,
        ?string $guestToken = null,
        int $width = 100,
        string $widthUnit = '%',
        int $height = 800,
        bool $showFilters = true,
        bool $expandFilters = false
    ): string {
        $url = $this->getDashboardEmbedUrl($dashboardId, $showFilters, $expandFilters);

        $iframe = sprintf(
            '<iframe src="%s" width="%d%s" height="%dpx" frameborder="0" allowfullscreen></iframe>',
            htmlspecialchars($url, ENT_QUOTES, 'UTF-8'),
            $width,
            $widthUnit,
            $height
        );

        if ($guestToken) {
            // Add authentication script if guest token provided
            $script = sprintf(
                '<script>
                    (function() {
                        const iframe = document.querySelector(\'iframe[src*="%d"]\');
                        if (iframe) {
                            iframe.addEventListener(\'load\', function() {
                                iframe.contentWindow.postMessage({
                                    type: \'auth\',
                                    token: \'%s\'
                                }, \'*\');
                            });
                        }
                    })();
                </script>',
                $dashboardId,
                htmlspecialchars($guestToken, ENT_QUOTES, 'UTF-8')
            );

            return $iframe . $script;
        }

        return $iframe;
    }

    /**
     * Generate dashboard embed URL.
     */
    public function getDashboardEmbedUrl(
        int $dashboardId,
        bool $showFilters = true,
        bool $expandFilters = false
    ): string {
        $mode = $showFilters ? ($expandFilters ? 2 : 1) : 3;

        return sprintf(
            '%s/superset/dashboard/%d/?standalone=%d',
            rtrim($this->baseUrl, '/'),
            $dashboardId,
            $mode
        );
    }

    /**
     * Generate chart embed URL.
     */
    public function getChartEmbedUrl(int $chartId, bool $standalone = true): string
    {
        $url = sprintf(
            '%s/superset/explore/?slice_id=%d',
            rtrim($this->baseUrl, '/'),
            $chartId
        );

        if ($standalone) {
            $url .= '&standalone=true';
        }

        return $url;
    }

    /**
     * Create guest token for embedding with RLS.
     */
    public function createGuestTokenWithRLS(
        int $dashboardId,
        array $rowLevelSecurity = [],
        array $user = [],
        int $expirySeconds = 300
    ): array {
        $resources = [
            [
                'type' => 'dashboard',
                'id' => (string) $dashboardId,
            ],
        ];

        $rls = [];
        foreach ($rowLevelSecurity as $clause) {
            $rls[] = ['clause' => $clause];
        }

        if (empty($user)) {
            $user = [
                'username' => 'guest_' . uniqid(),
                'first_name' => 'Guest',
                'last_name' => 'User',
            ];
        }

        return $this->client->createGuestToken($resources, $user, $rls);
    }

    /**
     * Generate complete embedded dashboard package.
     */
    public function generateEmbedPackage(
        int $dashboardId,
        array $rowLevelSecurity = [],
        array $user = [],
        array $options = []
    ): array {
        // Enable embedding
        $allowedDomains = $options['allowed_domains'] ?? [];
        $this->client->enableDashboardEmbedding($dashboardId, $allowedDomains);

        // Create guest token
        $tokenData = $this->createGuestTokenWithRLS(
            $dashboardId,
            $rowLevelSecurity,
            $user,
            $options['expiry_seconds'] ?? 300
        );

        $token = $tokenData['token'] ?? null;

        // Generate HTML
        $html = $this->generateDashboardEmbed(
            $dashboardId,
            $token,
            $options['width'] ?? 100,
            $options['width_unit'] ?? '%',
            $options['height'] ?? 800,
            $options['show_filters'] ?? true,
            $options['expand_filters'] ?? false
        );

        return [
            'dashboard_id' => $dashboardId,
            'token' => $token,
            'url' => $this->getDashboardEmbedUrl($dashboardId),
            'html' => $html,
            'expires_at' => $options['expiry_seconds'] ?? 300,
        ];
    }

    /**
     * Generate Superset Embedded SDK JavaScript code.
     */
    public function generateEmbeddedSDKCode(
        int $dashboardId,
        string $containerId,
        string $fetchTokenUrl
    ): string
    {
        return sprintf(
            '<script type="module">
                import { embedDashboard } from "https://unpkg.com/@superset-ui/embedded-sdk@0.1.0-alpha.10/bundle/index.js";

                embedDashboard({
                    id: "%s",
                    supersetDomain: "%s",
                    mountPoint: document.getElementById("%s"),
                    fetchGuestToken: async () => {
                        const response = await fetch("%s");
                        const data = await response.json();
                        return data.token;
                    },
                    dashboardUiConfig: {
                        hideTitle: false,
                        hideTab: false,
                        hideChartControls: false,
                    },
                });
            </script>',
            $dashboardId,
            rtrim($this->baseUrl, '/'),
            htmlspecialchars($containerId, ENT_QUOTES, 'UTF-8'),
            htmlspecialchars($fetchTokenUrl, ENT_QUOTES, 'UTF-8')
        );
    }
}
