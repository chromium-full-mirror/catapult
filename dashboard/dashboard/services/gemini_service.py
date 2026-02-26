# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import os
from google import genai

_DEFAULT_MODEL = 'gemini-3-flash-preview'


class GeminiServiceError(Exception):
  """Custom exception for GeminiService errors."""


def GetGeminiAnalysis(prompt, model=_DEFAULT_MODEL):
  """Sends a text prompt to Gemini using the Google GenAI SDK via Vertex AI.

  Args:
    prompt: The text prompt to send.
    model: The Gemini model name to use.

  Returns:
    A string containing Gemini's response, or an error message.
  """
  logging.info('GeminiService: Initializing GenAI client for Vertex AI.')

  try:
    # On App Engine, GOOGLE_CLOUD_PROJECT is usually set automatically.
    # GOOGLE_CLOUD_LOCATION and GOOGLE_GENAI_USE_VERTEXAI should be set via
    # environment variables in app.yaml.
    logging.debug(
        'GeminiService: Project: %s, Location: %s, Model: %s, Use Vertex AI: %s',
        os.getenv('GOOGLE_CLOUD_PROJECT'), os.getenv('GOOGLE_CLOUD_LOCATION'),
        model, os.getenv('GOOGLE_GENAI_USE_VERTEXAI'))

    # Initialize client using Vertex AI backend.
    client = genai.Client()

    logging.info('GeminiService: Requesting content generation...')
    response = client.models.generate_content(model=model, contents=prompt)

    if response and response.text:
      logging.info('GeminiService: Success.')
      return response.text

    logging.warning('GeminiService: Received empty response.')
    raise GeminiServiceError('Gemini returned an empty response.')

  except Exception as e:  # pylint: disable=broad-except
    logging.exception('GeminiService: Gemini Error: %s', str(e))
    raise GeminiServiceError('Failed to get analysis from Gemini: %s' %
                             str(e)) from e
