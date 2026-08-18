import unittest

from src.config import load_demo_config, load_domains, slugify


class ConfigTests(unittest.TestCase):
    def test_slugify_normalizes_names(self):
        self.assertEqual("product-operations", slugify("Product Operations"))

    def test_sample_demo_configuration_loads(self):
        config = load_demo_config()
        self.assertIn("app_title", config)
        self.assertTrue(config["sample_prompts"])

    def test_sample_domain_configuration_loads(self):
        domains = load_domains()
        self.assertEqual("example-domain", domains[0].key)
        self.assertIn("/v1/mcp/workspaces/", domains[0].server_url)


if __name__ == "__main__":
    unittest.main()
