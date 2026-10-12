"""Oracle Candidate Experience pages expose only a short blurb in HTML."""

import json
import unittest
from unittest.mock import patch

from job_url_analyzer import extract_from_html

ORACLE_URL = (
    "https://careers.oracle.com/en/sites/jobsearch/job/335818/"
    "?utm_medium=career+site&utm_source=job+alert"
)

PAGE_HTML = """
<html><head>
<meta property="og:title" content="Software Development Manager"/>
<meta property="og:description" content="Oracle Health Applications &amp; Infrastructure is building the next generation of cloud services. This short blurb is all the HTML page includes."/>
<meta property="og:site_name" content="Oracle"/>
<link rel="icon" href="https://eeho.fa.us2.oraclecloud.com/hcmRestApi/CandidateExperience/siteFavicon/favicon-16x16.png?siteNumber=CX_45001&amp;size=16x16"/>
</head><body></body></html>
"""

API_PAYLOAD = {
    "items": [
        {
            "Id": "335818",
            "Title": "Software Development Manager",
            "Organization": "",
            "ExternalContactName": "",
            "ShortDescriptionStr": (
                "Oracle Health Applications & Infrastructure is building the "
                "next generation of cloud services. This short blurb is all "
                "the HTML page includes."
            ),
            "ExternalDescriptionStr": (
                "<p>At Oracle Health, our mission is to improve healthcare.</p>"
            ),
            "ExternalResponsibilitiesStr": (
                "<div><strong>Responsibilities</strong></div>"
                "<ul><li>Grow and mentor engineering teams.</li></ul>"
                "<div><strong>Qualifications</strong></div>"
                "<ul><li>5+ years leading engineering teams.</li></ul>"
                "<div><strong>Preferred qualifications</strong></div>"
                "<ul><li>Experience with authorization systems.</li></ul>"
                "<p><strong>About the work</strong></p>"
                "<p>The Authorization team protects healthcare data.</p>"
            ),
            "ExternalQualificationsStr": (
                "<p>Disclaimer:</p><p>US: Hiring Range in USD from: "
                "$112,800 to $264,100 per annum.</p>"
                "<p>Career Level - M2</p>"
            ),
            "CorporateDescriptionStr": (
                "<p>Only Oracle brings together the data and infrastructure.</p>"
            ),
        }
    ]
}


class TestOracleCeJobExtract(unittest.TestCase):
    def test_uses_requisition_api_instead_of_og_description(self):
        with patch("job_url_analyzer.requests.get") as get:
            response = get.return_value
            response.raise_for_status.return_value = None
            response.json.return_value = API_PAYLOAD

            result = extract_from_html(PAGE_HTML, ORACLE_URL)

        self.assertEqual(result.method, "beautifulsoup-oracle-ce")
        self.assertEqual(result.company, "Oracle")
        self.assertEqual(result.job_title, "Software Development Manager")
        self.assertTrue(result.is_complete)
        description = result.job_description or ""
        self.assertIn("At Oracle Health, our mission", description)
        self.assertIn("Responsibilities", description)
        self.assertIn("Grow and mentor engineering teams.", description)
        self.assertIn("Preferred qualifications", description)
        self.assertIn("About the work", description)
        self.assertIn("$112,800 to $264,100", description)
        self.assertIn("Career Level - M2", description)
        self.assertIn("About Us", description)
        self.assertIn("Only Oracle brings together", description)
        self.assertNotIn("this short blurb is all the HTML page includes", description.lower())
        self.assertGreater(len(description), 400)

        api_url = get.call_args.args[0]
        self.assertIn("recruitingCEJobRequisitionDetails", api_url)
        self.assertIn("Id=335818", api_url)
        self.assertIn("siteNumber=CX_45001", api_url)
        self.assertIn("eeho.fa.us2.oraclecloud.com", api_url)

    def test_non_oracle_page_does_not_call_requisition_api(self):
        html = """
        <html><head>
        <meta property="og:title" content="Engineer"/>
        <meta property="og:description" content="A long enough job description for the generic parser to keep as the posting body without calling another API."/>
        <meta property="og:site_name" content="Example Co"/>
        </head><body></body></html>
        """
        with patch("job_url_analyzer.requests.get") as get:
            result = extract_from_html(
                html, "https://example.com/jobs/12345"
            )
        get.assert_not_called()
        self.assertNotEqual(result.method, "beautifulsoup-oracle-ce")

    def test_api_failure_falls_back_to_page_html(self):
        with patch("job_url_analyzer.requests.get", side_effect=OSError("down")):
            result = extract_from_html(PAGE_HTML, ORACLE_URL)
        self.assertNotEqual(result.method, "beautifulsoup-oracle-ce")
        self.assertIn("short blurb", result.job_description or "")


if __name__ == "__main__":
    unittest.main()
