<?php

namespace GAuth;

/**
 * A class for generating the codes compatible with the Google Authenticator
 * clients.
 *
 * NOTE: A lot of the logic from this class has been borrowed from this class:
 * http://www.idontplaydarts.com/wp-content/uploads/2011/07/ga.php_.txt
 *
 * @author Chris Cornutt <ccornutt@phpdeveloper.org>
 * @package GAuth
 * @license MIT
 */

class Auth
{
    /**
     * Internal lookup table
     * @var array
     */
    private $lookup = array();

    /**
     * Initialization key
     * @var string
     */
    private $initKey = null;

    /**
     * Seconds between key refreshes
     * @var integer
     */
    private $refreshSeconds = 30;

    /**
     * Length of codes to generate
     * @var integer
     */
    private $codeLength = 6;

    /**
     * Range plus/minus for "window of opportunity" on allowed codes
     * @var integer
     */
    private $range = 2;

    /**
     * Initialize the object and set up the lookup table
     *     Optionally the Initialization key
     *
     * @param string $initKey Initialization key
     */
    public function __construct($initKey = null)
    {
        $this->buildLookup();

        if ($initKey !== null) {
            $this->setInitKey($initKey);
        }
    }

    /**
     * Build the base32 lookup table
     *
     * @return null
     */
    public function buildLookup()
    {
        $lookup = array_combine(
            array_merge(range('A', 'Z'), range(2, 7)),
            range(0, 31)
        );
        $this->setLookup($lookup);
    }

    /**
     * Get the current "range" value
     * @return integer Range value
     */
    public function getRange()
    {
        return $this->range;
    }

    /**
     * Set the "range" value
     *
     * @param integer $range Range value
     * @return \GAuth\Auth instance
     */
    public function setRange($range)
    {
        if (!is_numeric($range)) {
            throw new \InvalidArgumentException('Invalid window range');
        }
        $this->range = $range;
        return $this;
    }

    /**
     * Set the initialization key for the object
     *
     * @param string $key Initialization key
     * @throws \InvalidArgumentException If hash is not valid base32
     * @return \GAuth\Auth instance
     */
    public function setInitKey($key)
    {
        if (preg_match('/^['.implode('', array_keys($this->getLookup())).']+$/', $key) == false) {
            throw new \InvalidArgumentException('Invalid base32 hash!');
        }
        $this->initKey = $key;
        return $this;
    }

    /**
     * Get the current Initialization key
     *
     * @return string Initialization key
     */
    public function getInitKey()
    {
        return $this->initKey;
    }

    /**
     * Set the contents of the internal lookup table
     *
     * @param array $lookup Lookup data set
     * @throws \InvalidArgumentException If lookup given is not an array
     * @return \GAuth\Auth instance
     */
    public function setLookup($lookup)
    {
        if (!is_array($lookup)) {
            throw new \InvalidArgumentException('Lookup value must be an array');
        }
        $this->lookup = $lookup;
        return $this;
    }

    /**
     * Get the current lookup data set
     *
     * @return array Lookup data
     */
    public function getLookup()
    {
        return $this->lookup;
    }

    /**
     * Get the number of seconds for code refresh currently set
     *
     * @return integer Refresh in seconds
     */
    public function getRefresh()
    {
        return $this->refreshSeconds;
    }

    /**
     * Set the number of seconds to refresh codes
     *
     * @param integer $seconds Seconds to refresh
     * @throws \InvalidArgumentException If seconds value is not numeric
     * @return \GAuth\Auth instance
     */
    public function setRefresh($seconds)
    {
        if (!is_numeric($seconds)) {
            throw new \InvalidArgumentException('Seconds must be numeric');
        }
        $this->refreshSeconds = $seconds;
        return $this;
    }

    /**
     * Get the current length for generated codes
     *
     * @return integer Code length
     */
    public function getCodeLength()
    {
        return $this->codeLength;
    }

    /**
     * Set the length of the generated codes
     *
     * @param integer $length Code length
     * @return \GAuth\Auth instance
     */
    public function setCodeLength($length)
    {
        $this->codeLength = $length;
        return $this;
    }

    /**
     * Validate the given code
     *
     * @param string $code Code entered by user
     * @param string $initKey Initialization key
     * @param string $timestamp Timestamp for calculation
     * @param integer $range Seconds before/after to validate hash against
     * @throws \InvalidArgumentException If incorrect code length
     * @return boolean Pass/fail of validation
     */
    public function validateCode($code, $initKey = null, $timestamp = null, $range = null)
    {
        if (strlen($code) !== $this->getCodeLength()) {
            throw new \InvalidArgumentException('Incorrect code length');
        }

        $range = ($range == null) ? $this->getRange() : $range;
        $timestamp = ($timestamp == null) ? $this->generateTimestamp() : $timestamp;
        $initKey = ($initKey == null) ? $this->getInitKey() : $initKey;

        $binary = $this->base32_decode($initKey);

        for ($time = ($timestamp - $range); $time <= ($timestamp + $range); $time++) {
            if ($this->generateOneTime($binary, $time) == $code) {
                return true;
            }
        }
        return false;
    }

    /**
     * Generate a one-time code
     *
     * @param string $initKey Initialization key [optional]
     * @param string $timestamp Timestamp for calculation [optional]
     * @return string Geneerated code/hash
     */
    public function generateOneTime($initKey = null, $timestamp = null)
    {
        $initKey = ($initKey == null) ? $this->getInitKey() : $initKey;
        $timestamp = ($timestamp == null) ? $this->generateTimestamp() : $timestamp;

        $hash = hash_hmac (
            'sha1',
            pack('N*', 0) . pack('N*', $timestamp),
            $initKey,
            true
        );

        return str_pad($this->truncateHash($hash), $this->getCodeLength(), '0', STR_PAD_LEFT);
    }

    /**
     * Generate a code/hash
     *     Useful for making Initialization codes
     *
     * @param integer $length Length for the generated code
     * @return string Generated code
     * @throws \Exception if it's unable to generate sufficient randomness.
     */
    public function generateCode($length = 16)
    {
        $lookup = implode('', array_keys($this->getLookup()));
        $code = '';

        try {
            for ($i = 0; $i < $length; $i++) {
                $code .= $lookup[rand(0, strlen($lookup) - 1)];
            }
        } catch(\Exception $e) {
            throw $e; //return the exception to implementors of gauth so they can handle it
        }


        return $code;
    }

    /**
     * Generate the timestamp for the calculation
     *
     * @return integer Timestamp
     */
    public function generateTimestamp()
    {
        return floor(microtime(true)/$this->getRefresh());
    }

    /**
     * Generate the URL for the Google Charts API to make the QR code
     * To use in an image tag:
     *
     * '<img src="data:image/png;base64,'.base64_encode($data).'"/>
     *
     * @param string $holder Account identifier (email, username, etc)
     * @param string $name Name of the application
     * @param integer $size Height x Width in pixels of the resulting image
     */
    public function generateQrImage($holder, $name, $size = 30)
    {
      $data = 'otpauth://totp/'.$name.':'.$holder.'?secret='.$this->getInitKey();

      $renderer = new \BaconQrCode\Renderer\Image\Png();
      $renderer->setMargin(0)
        ->setHeight($size)
        ->setWidth($size);
      $writer = new \BaconQrCode\Writer($renderer);

      return $writer->writeString($data);
    }

    /**
     * Truncate the given hash down to just what we need
     *
     * @param string $hash Hash to truncate
     * @return string Truncated hash value
     */
    public function truncateHash($hash)
    {
        $offset = ord($hash[19]) & 0xf;

        return (
            ((ord($hash[$offset+0]) & 0x7f) << 24 ) |
            ((ord($hash[$offset+1]) & 0xff) << 16 ) |
            ((ord($hash[$offset+2]) & 0xff) << 8 ) |
            (ord($hash[$offset+3]) & 0xff)
        ) % pow(10, $this->getCodeLength());
    }

    /**
     * Base32 decoding function
     *
     * @param string base32 encoded hash
     * @throws \InvalidArgumentException When hash is not valid
     * @return string Binary value of hash
     */
    public function base32_decode($hash)
    {
        $lookup = $this->getLookup();

        if (preg_match('/^['.implode('', array_keys($lookup)).']+$/', $hash) == false) {
            throw new \InvalidArgumentException('Invalid base32 hash!');
        }

        $hash = strtoupper($hash);
        $buffer = 0;
        $length = 0;
        $binary = '';

        for ($i = 0; $i < strlen($hash); $i++) {
            $buffer = $buffer << 5;
            $buffer += $lookup[$hash[$i]];
            $length += 5;

            if ($length >= 8) {
                $length -= 8;
                $binary .= chr(($buffer & (0xFF << $length)) >> $length);
            }
        }

        return $binary;
    }

}
