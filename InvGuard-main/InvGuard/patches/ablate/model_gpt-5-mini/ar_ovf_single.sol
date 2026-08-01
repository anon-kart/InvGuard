/*
 * @source: https://github.com/ConsenSys/evm-analyzer-benchmark-suite
 * @author: Suhabe Bugrara
 * @vulnerable_at_lines: 18,24,30,36,42,48
 */

//Single transaction overflow
//Post-transaction effect: overflow escapes to publicly-readable storage

pragma solidity ^0.4.23;

contract IntegerOverflowSingleTransaction {
    uint public count = 1;

    // ADD overflow with result stored in state variable.
    function overflowaddtostate(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent overflow: ensure input <= max_uint - count
        require(input <= uint256(-1) - count);
        count += input;
    }

    // MUL overflow with result stored in state variable.
    function overflowmultostate(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent overflow: if count != 0, ensure input <= max_uint / count
        require(count == 0 || input <= uint256(-1) / count);
        count *= input;
    }

    // Underflow with result stored in state variable.
    function underflowtostate(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent underflow: input must be <= count
        require(input <= count);
        count -= input;
    }

    // ADD Overflow, no effect on state.
    function overflowlocalonly(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent overflow for local addition
        require(input <= uint256(-1) - count);
        uint res = count + input;
    }

    // MUL Overflow, no effect on state.
    function overflowmulocalonly(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent overflow for local multiplication
        require(count == 0 || input <= uint256(-1) / count);
        uint res = count * input;
    }

    // Underflow, no effect on state.
    function underflowlocalonly(uint256 input) public {
        // <yes> <report> ARITHMETIC
        // Prevent underflow for local subtraction
        require(input <= count);
       	uint res = count - input;
    }

}